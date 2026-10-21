import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

def test_app_routes():
    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths", {})
    print(f"Total registered API routes in OpenAPI: {len(paths)}")
    
    assert "/health" in paths
    assert "/api/v1/catalog/products" in paths
    assert "/api/v1/suppliers" in paths
    assert "/api/v1/kaspi/feed/{feed_slug}.xml" in paths
    assert "/api/v1/orders" in paths
    assert "/api/v1/orders/analytics/summary" in paths
    print("  [OK] All core business routes and Kaspi XML endpoints verified.")

if __name__ == "__main__":
    test_app_routes()
