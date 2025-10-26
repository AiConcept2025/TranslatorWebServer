"""
Fix test subscription for Iris Trading to have proper usage_periods.
Run this script to add/update usage_periods with 1000 allocated units.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from app.database import database

async def fix_subscription():
    """Fix the test subscription to have proper usage_periods."""
    try:
        # Connect to MongoDB
        await database.connect()
        print("✓ Connected to MongoDB")
        
        # Find company
        company_id_str = "68ec42a48ca6a1781d9fe5c9"
        company_id = ObjectId(company_id_str)
        
        company = await database.companies.find_one({"_id": company_id})
        if not company:
            print(f"❌ Company not found with ID: {company_id_str}")
            return
        
        print(f"✓ Found company: {company.get('company_name')}")
        
        # Find subscription
        subscription = await database.subscriptions.find_one({"company_id": company_id})
        
        if not subscription:
            print(f"❌ No subscription found for company {company_id_str}")
            print("Creating new subscription...")
            
            # Create new subscription with usage period
            new_subscription = {
                "company_id": company_id,
                "subscription_unit": "page",
                "units_per_subscription": 1000,
                "price_per_unit": 0.10,
                "promotional_units": 100,
                "status": "active",
                "start_date": datetime.now(timezone.utc),
                "end_date": datetime.now(timezone.utc) + timedelta(days=365),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "usage_periods": [{
                    "period_start": datetime.now(timezone.utc),
                    "period_end": datetime.now(timezone.utc) + timedelta(days=30),
                    "units_allocated": 1000,
                    "units_used": 0,
                    "units_remaining": 1000,
                    "promotional_units_used": 0,
                    "last_updated": datetime.now(timezone.utc)
                }]
            }
            
            result = await database.subscriptions.insert_one(new_subscription)
            print(f"✓ Created new subscription with ID: {result.inserted_id}")
            print(f"  Units allocated: 1000 pages")
            
        else:
            print(f"✓ Found existing subscription: {subscription.get('_id')}")
            
            # Check if usage_periods exists
            usage_periods = subscription.get("usage_periods", [])
            
            if not usage_periods or len(usage_periods) == 0:
                print("⚠ Subscription has no usage_periods, adding one...")
                
                # Add usage period
                new_usage_period = {
                    "period_start": datetime.now(timezone.utc),
                    "period_end": datetime.now(timezone.utc) + timedelta(days=30),
                    "units_allocated": 1000,
                    "units_used": 0,
                    "units_remaining": 1000,
                    "promotional_units_used": 0,
                    "last_updated": datetime.now(timezone.utc)
                }
                
                result = await database.subscriptions.update_one(
                    {"_id": subscription["_id"]},
                    {
                        "$set": {
                            "usage_periods": [new_usage_period],
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                print(f"✓ Added usage_period with 1000 units")
                print(f"  Modified count: {result.modified_count}")
                
            else:
                # Calculate totals
                total_allocated = sum(p.get("units_allocated", 0) for p in usage_periods)
                total_used = sum(p.get("units_used", 0) for p in usage_periods)
                total_remaining = sum(p.get("units_remaining", 0) for p in usage_periods)
                
                print(f"✓ Subscription already has {len(usage_periods)} usage_period(s)")
                print(f"  Total allocated: {total_allocated} pages")
                print(f"  Total used: {total_used} pages")
                print(f"  Total remaining: {total_remaining} pages")
                
                if total_remaining == 0:
                    print("⚠ No units remaining, resetting to 1000...")
                    # Reset the first period
                    usage_periods[0]["units_allocated"] = 1000
                    usage_periods[0]["units_used"] = 0
                    usage_periods[0]["units_remaining"] = 1000
                    usage_periods[0]["last_updated"] = datetime.now(timezone.utc)
                    
                    result = await database.subscriptions.update_one(
                        {"_id": subscription["_id"]},
                        {
                            "$set": {
                                "usage_periods": usage_periods,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                    print(f"✓ Reset units to 1000")
                    print(f"  Modified count: {result.modified_count}")
        
        # Verify the final state
        print("\n" + "="*60)
        print("VERIFICATION:")
        subscription = await database.subscriptions.find_one({"company_id": company_id})
        if subscription:
            usage_periods = subscription.get("usage_periods", [])
            total_allocated = sum(p.get("units_allocated", 0) for p in usage_periods)
            total_used = sum(p.get("units_used", 0) for p in usage_periods)
            total_remaining = sum(p.get("units_remaining", 0) for p in usage_periods)
            
            print(f"Company: {company.get('company_name')}")
            print(f"Company ID: {company_id}")
            print(f"Subscription ID: {subscription.get('_id')}")
            print(f"Status: {subscription.get('status')}")
            print(f"Price per unit: ${subscription.get('price_per_unit')}")
            print(f"Total allocated: {total_allocated} pages")
            print(f"Total used: {total_used} pages")
            print(f"Total remaining: {total_remaining} pages")
            print("="*60)
        
        await database.disconnect()
        print("\n✓ Done!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_subscription())
