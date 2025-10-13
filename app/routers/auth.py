"""
Authentication API endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import json
import logging
import secrets
import hashlib
from datetime import datetime, timedelta

router = APIRouter(prefix="/login", tags=["Authentication"])

class CorporateLoginRequest(BaseModel):
    """Corporate login request model."""
    company_name: str = Field(..., alias='companyName', min_length=1)
    password: str = Field(..., min_length=6)
    user_full_name: str = Field(..., alias='userFullName', min_length=1)
    user_email: EmailStr = Field(..., alias='userEmail')
    login_date_time: str = Field(..., alias='loginDateTime')

    model_config = {
        'populate_by_name': True  # Accept both camelCase and snake_case
    }

class CorporateLoginResponse(BaseModel):
    """Corporate login response model."""
    success: bool
    message: str
    data: dict

@router.post("/corporate")
async def corporate_login(raw_request: Request):
    """
    Corporate login endpoint.

    Authenticates corporate users and returns an authentication token.
    """
    print("\n" + "=" * 80)
    print("🔐 CORPORATE LOGIN - INCOMING REQUEST")
    print("=" * 80)

    # Log raw incoming request
    try:
        raw_body = await raw_request.body()
        raw_json = raw_body.decode('utf-8')
        print("📥 INCOMING PAYLOAD:")
        print(raw_json)

        # Parse JSON
        json_data = json.loads(raw_json)
        print("\n📋 PARSED JSON:")
        print(json.dumps(json_data, indent=2))

    except Exception as e:
        print(f"❌ ERROR reading request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request format")

    # Validate with Pydantic model
    try:
        request = CorporateLoginRequest(**json_data)
    except Exception as e:
        print(f"❌ VALIDATION ERROR: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    print("\n" + "-" * 80)
    print("✅ PARSED FIELDS:")
    print("-" * 80)
    print(f"Company Name:      {request.company_name}")
    print(f"User Full Name:    {request.user_full_name}")
    print(f"User Email:        {request.user_email}")
    print(f"Login Date/Time:   {request.login_date_time}")
    print(f"Password:          {'*' * len(request.password)} (hidden)")
    print("-" * 80)

    try:
        # Generate authentication token
        # Using a combination of user info and timestamp for uniqueness
        token_base = f"{request.user_email}:{request.company_name}:{request.login_date_time}:{secrets.token_urlsafe(32)}"
        auth_token = hashlib.sha256(token_base.encode()).hexdigest()

        # Calculate token expiration (24 hours from now)
        expiration_time = datetime.utcnow() + timedelta(hours=24)

        print(f"\n🔑 AUTHENTICATION TOKEN GENERATED")
        print(f"   Token: {auth_token[:16]}...{auth_token[-16:]}")
        print(f"   Expires: {expiration_time.isoformat()}Z")

        # Log authentication success
        logging.info(f"Corporate login successful - Company: {request.company_name}, User: {request.user_email}")

        # Prepare response
        response_content = {
            "success": True,
            "message": "Corporate login successful",
            "data": {
                "authToken": auth_token,
                "tokenType": "Bearer",
                "expiresIn": 86400,  # 24 hours in seconds
                "expiresAt": expiration_time.isoformat() + "Z",
                "user": {
                    "fullName": request.user_full_name,
                    "email": request.user_email,
                    "company": request.company_name
                },
                "loginDateTime": request.login_date_time
            }
        }

        print("\n" + "=" * 80)
        print("📤 OUTGOING RESPONSE:")
        print("=" * 80)
        print(json.dumps(response_content, indent=2))
        print("=" * 80 + "\n")

        return JSONResponse(content=response_content)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        logging.error(f"Corporate login error: {e}", exc_info=True)

        error_response = {
            "success": False,
            "error": {
                "code": 500,
                "message": f"Login processing failed: {str(e)}",
                "type": "internal_error"
            }
        }

        print("\n" + "=" * 80)
        print("📤 OUTGOING ERROR RESPONSE:")
        print("=" * 80)
        print(json.dumps(error_response, indent=2))
        print("=" * 80 + "\n")

        raise HTTPException(
            status_code=500,
            detail=f"Login processing failed: {str(e)}"
        )
