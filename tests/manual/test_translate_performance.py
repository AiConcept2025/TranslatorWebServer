import asyncio
import httpx
import base64
import time
from datetime import datetime

async def test_translate_endpoint():
    """Test the /translate endpoint with accurate page counting"""
    
    # Create a simple PDF file content (this is a minimal PDF with 1 page)
    # This is a base64 encoded single-page PDF
    pdf_content_base64 = "JVBERi0xLjQKJcOkw7zDtsOfCjIgMCBvYmoKPDwvTGVuZ3RoIDMgMCBSL0ZpbHRlci9GbGF0ZURlY29kZT4+CnN0cmVhbQp4nDPQM1Qo5ypUMABCM0MjBXNDSysFQwsDQysFIwUzS0tLMwWzIDMDSwsF03QFQ12FgqLU4pLM9Jx8BQAzEQwBCmVuZHN0cmVhbQplbmRvYmoKCjMgMCBvYmoKNDkKZW5kb2JqCgo1IDAgb2JqCjw8L0xlbmd0aCA2IDAgUi9GaWx0ZXIvRmxhdGVEZWNvZGUvTGVuZ3RoMSAzNjY4Pj4Kc3RyZWFtCnic7VdbbxxVHD6z2Xub2Tuz9+3e774zs7OzO3uZ3b3N7HVv3dZ2U6dxEtqkTWnTUkQpRBQhASIqKBUECQkQCAleUKX2oYj3PiB45IGHR4QEQrwgHnnmzHrblCCkSrx4f8zsfP/lO8c/c84AXD1rHYD5MbZKpFdY+RCU8VwFkGusvM/KSxD8JCsfgD3WUEsUL0bxa1D9UFjHoP+msPUH2LOEDXlQeyWsfRdUl3y7wOZlVh+D4/eCfgCGluLrIgTfEtbvgsE7bNwG1ddZ+SZc6MWlz0P6LVb+GUbfx6Vn0Lem4yZc3hHWN+DEAr7ugJHHcGmTlb+A1CJbZ+DPW7j0/9g6Azd+jUs/hbN1Vm4B3+TK67D/e6z8E7g7uPQxOP4xljxrXW/BHe+w8jY0l9k6Cc13Qh+B/sXY+hGUv2L1D+H4G2ydgP4NK78HJ77H1hu4dBV2vw2OXgPzq/j6OpS/Y/UXoP4D3n4MK7+y8jJMfomtH0L5ZzzfjxU3wN6/YOsG9N+Erddg/w5bx2HqC2x9Dubnce9FOPwlvL4Cv97G88+h/BWefw31v/D5r6H8O56vwv6/8fkaHL+L5+tQ/xfrX4fD/+D5Otz4F+v/hv1/4fkGlP/F863nW8+3nm+Bd3m+x/M9nu/xfI/nezz/v+cH+HoD/vwfP38D/vyf/7+z8zzO87jeZ2F8npXPQvJZVn4OVl5g5RcgfYGVX4SVl1j5ZTh5ipVfgdQpVj4Nh19l5degfJqVz8DsGVY+C+fOsfJ5OH+BlS/A7CIrvw6rl1j5Dah/hb3fgfI3bJ2GcBNbZ6C5wdY5aF7E83UovY6nL0Hzdbx9HU5cgdPXYP8aHL4CrbfxeB2O34HDN2H6Jhy/BZP3YOoWTN+C6dsweQ9O3IfT92DyAZx+AFP3YeoBTD2EqYcw9QCmHsLUA5i6D1P3YfIBTN6HyfswdQ8mH8DkfZi8D5P3YfIeTN6DyXsweQ8m78LkPTh9D07fg8k7MHkHJu/A5D04fg9O34HTd+H0XZi8C5N34PQdOH0HTt+F03fh9F04fRdO34XTd+H0XTh9F07fhdN34fRdOH0XTt+F03dh8h5M3oPJezB5DybvweQ9mLwHk/dg8h5M3oPJezB5DybvweQ9mLwHk/dg8h5M3oPJezB5DybvweQ9mLwHk/dg8h5M3oPJezB5DybvweQ9mLwHk/dg8h5M3oPJezB5DybvweQ9mLwLk3dh8i5M3oXJu7zuI+cXlTn/E5QPAABN"
    
    # API endpoint
    url = "http://localhost:8000/translate"
    
    # Test data - simulating a file upload with the correct format
    import uuid
    test_data = {
        "files": [
            {
                "id": str(uuid.uuid4()),
                "name": "test_document.pdf",
                "type": "application/pdf",
                "content": pdf_content_base64,
                "size": len(base64.b64decode(pdf_content_base64))
            }
        ],
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "email": "danishevsky@gmail.com"
    }
    
    # Get JWT token for enterprise admin user
    token = "mCh2GVXFYPrnPR_PJJYVYLxFMcCsEQWq-wi87zvai9w"  # Known test token
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("Testing /translate endpoint with accurate page counting")
    print("=" * 80)
    print(f"\n📋 Test file: test_document.pdf")
    print(f"📦 File size: {test_data['files'][0]['size']} bytes")
    print(f"👤 User: danishevsky@gmail.com (Enterprise Admin)")
    print(f"🌍 Translation: en -> es\n")
    
    # Measure total response time
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("⏳ Sending request to /translate endpoint...")
            response = await client.post(url, json=test_data, headers=headers)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"\n✅ Response received in {elapsed_time:.3f} seconds")
            print(f"📊 HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n📄 Response Data:")
                print(f"  - Success: {result.get('success')}")

                # Parse nested data structure
                data = result.get('data', {})
                print(f"  - Storage ID: {data.get('id')}")
                print(f"  - Status: {data.get('status')}")
                print(f"  - Message: {data.get('message')}")

                # Files information
                if 'files' in data:
                    files_info = data['files']
                    print(f"\n📁 Files Summary:")
                    print(f"  - Total: {files_info.get('total_files')}")
                    print(f"  - Successful: {files_info.get('successful_uploads')}")
                    print(f"  - Failed: {files_info.get('failed_uploads')}")

                    stored_files = files_info.get('stored_files', [])
                    print(f"\n📁 Stored Files ({len(stored_files)}):")
                    for f in stored_files:
                        print(f"  - {f['filename']}: {f['page_count']} pages (status: {f['status']})")

                # Pricing information
                if 'pricing' in data:
                    pricing = data['pricing']
                    print(f"\n💵 Pricing:")
                    print(f"  - Total Pages: {pricing.get('total_pages')}")
                    print(f"  - Price Per Page: ${pricing.get('price_per_page')}")
                    print(f"  - Total Amount: ${pricing.get('total_amount'):.2f}")
                    print(f"  - Currency: {pricing.get('currency')}")
                    print(f"  - Customer Type: {pricing.get('customer_type')}")
                    print(f"  - Transaction IDs: {pricing.get('transaction_ids', [])}")

                # Subscription validation
                if 'subscription' in data:
                    subscription = data['subscription']
                    print(f"\n💳 Subscription Validation:")
                    print(f"  - Status: {subscription.get('status')}")
                    print(f"  - User Permission: {subscription.get('user_permission')}")
                    if subscription.get('info'):
                        info = subscription['info']
                        print(f"  - Units Remaining: {info.get('units_remaining')}")
                        print(f"  - Units Required: {info.get('units_required')}")
                        print(f"  - Unit Type: {info.get('subscription_unit')}")

                print(f"\n⏱️  Performance: {elapsed_time:.3f}s")
                if elapsed_time < 1.0:
                    print(f"✅ Performance EXCELLENT (< 1 second)")
                elif elapsed_time < 3.0:
                    print(f"✅ Performance GOOD (< 3 seconds)")
                else:
                    print(f"⚠️  Performance NEEDS IMPROVEMENT (> 3 seconds)")
                    print(f"    Note: Time includes file upload to Google Drive + accurate page counting")
                    
            else:
                print(f"\n❌ Error Response:")
                print(response.text)
                
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n❌ Error after {elapsed_time:.3f}s: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_translate_endpoint())
