import io
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.modules.suppliers.models import Supplier, SupplierOffer
from app.modules.catalog.models import MasterProduct
from app.modules.suppliers.parser import SupplierFeedParser
from app.modules.catalog.matching import SKUMatchingEngine

router = APIRouter(prefix="/suppliers", tags=["Suppliers & Feed Ingestion"])


class SupplierCreate(BaseModel):
    name: str
    code: str
    delivery_days: int = 1
    priority: int = 1


class SupplierResponse(SupplierCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class MatchingReviewItem(BaseModel):
    offer_id: uuid.UUID
    supplier_name: str
    supplier_sku: str
    raw_title: str
    cost_price: float
    stock_quantity: int
    suggested_master_id: Optional[uuid.UUID] = None
    suggested_master_title: Optional[str] = None
    confidence_score: float
    match_type: str


@router.get("", response_model=List[SupplierResponse])
async def list_suppliers(
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Supplier).where(Supplier.organization_id == organization_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=SupplierResponse)
async def create_supplier(
    payload: SupplierCreate,
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    supplier = Supplier(
        organization_id=organization_id,
        name=payload.name,
        code=payload.code,
        delivery_days=payload.delivery_days,
        priority=payload.priority
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.post("/{supplier_id}/upload-feed")
async def upload_supplier_feed(
    supplier_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and stream-parse supplier price-list (CSV or XLSX).
    Runs multi-stage cascade matching (Barcode -> SKU -> Fuzzy Similarity).
    """
    supplier_res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = supplier_res.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    file_bytes = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        items_generator = SupplierFeedParser.parse_excel_stream(file_bytes)
    else:
        text_content = file_bytes.decode("utf-8", errors="ignore")
        items_generator = SupplierFeedParser.parse_csv_stream(io.StringIO(text_content))

    # Fetch candidate MasterProducts for intelligent cascade matching
    master_stmt = select(MasterProduct).where(MasterProduct.organization_id == supplier.organization_id)
    candidates = (await db.execute(master_stmt)).scalars().all()

    processed_count = 0
    auto_matched_count = 0
    pending_review_count = 0

    for item in items_generator:
        sku = item["supplier_sku"]
        raw_title = item["raw_title"]
        barcode = item.get("barcode")
        brand = item.get("raw_brand")

        # Run Cascade Matching Engine
        matched_prod, confidence, match_type, match_status = SKUMatchingEngine.match_offer(
            offer_title=raw_title,
            offer_barcode=barcode,
            offer_sku=sku,
            offer_brand=brand,
            candidates=candidates
        )

        if match_status == "confirmed":
            auto_matched_count += 1
        elif match_status == "pending_review":
            pending_review_count += 1

        # Upsert offer
        offer_stmt = select(SupplierOffer).where(
            SupplierOffer.supplier_id == supplier.id,
            SupplierOffer.supplier_sku == sku
        )
        existing_offer = (await db.execute(offer_stmt)).scalar_one_or_none()

        if existing_offer:
            existing_offer.cost_price = item["cost_price"]
            existing_offer.stock_quantity = item["stock_quantity"]
            existing_offer.raw_title = raw_title
            existing_offer.barcode = barcode
            if matched_prod and match_status == "confirmed":
                existing_offer.master_product_id = matched_prod.id
            existing_offer.match_confidence = confidence
            existing_offer.match_type = match_type
            existing_offer.match_status = match_status
        else:
            new_offer = SupplierOffer(
                supplier_id=supplier.id,
                master_product_id=matched_prod.id if (matched_prod and match_status == "confirmed") else None,
                supplier_sku=sku,
                raw_title=raw_title,
                raw_brand=brand,
                barcode=barcode,
                cost_price=item["cost_price"],
                stock_quantity=item["stock_quantity"],
                match_confidence=confidence,
                match_type=match_type,
                match_status=match_status
            )
            db.add(new_offer)

        processed_count += 1

    await db.commit()

    return {
        "status": "success",
        "supplier": supplier.name,
        "processed_offers": processed_count,
        "auto_confirmed_matches": auto_matched_count,
        "pending_human_review": pending_review_count
    }


@router.get("/matching/pending-review", response_model=List[MatchingReviewItem])
async def list_pending_matches(
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns supplier offers that have partial / fuzzy matches (confidence 45-74%)
    and need human manager confirmation.
    """
    stmt = (
        select(SupplierOffer)
        .join(Supplier)
        .where(
            Supplier.organization_id == organization_id,
            SupplierOffer.match_status == "pending_review"
        )
        .options(selectinload(SupplierOffer.supplier))
    )
    offers = (await db.execute(stmt)).scalars().all()

    # Get master candidates for titles
    master_stmt = select(MasterProduct).where(MasterProduct.organization_id == organization_id)
    masters = {m.id: m.title for m in (await db.execute(master_stmt)).scalars().all()}

    results = []
    for o in offers:
        results.append(MatchingReviewItem(
            offer_id=o.id,
            supplier_name=o.supplier.name if o.supplier else "Unknown",
            supplier_sku=o.supplier_sku,
            raw_title=o.raw_title,
            cost_price=float(o.cost_price),
            stock_quantity=o.stock_quantity,
            suggested_master_id=o.master_product_id,
            suggested_master_title=masters.get(o.master_product_id, "Candidate SKU"),
            confidence_score=float(o.match_confidence or 0.0),
            match_type=o.match_type or "fuzzy"
        ))
    return results


@router.post("/matching/{offer_id}/confirm")
async def confirm_offer_match(
    offer_id: uuid.UUID,
    master_product_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Approves match between a supplier offer and a MasterProduct with 1 click.
    """
    offer_stmt = select(SupplierOffer).where(SupplierOffer.id == offer_id)
    offer = (await db.execute(offer_stmt)).scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    offer.master_product_id = master_product_id
    offer.match_status = "confirmed"
    offer.match_type = "manual_confirmed"
    offer.match_confidence = 1.0

    await db.commit()
    return {"status": "confirmed", "offer_id": str(offer_id), "master_product_id": str(master_product_id)}
