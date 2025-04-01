import httpx
import asyncio
import json
from pprint import pprint

BASE_URL = "http://localhost:8000"

async def test_login_invalid_credentials():
    """Test login with invalid credentials to trigger error handling"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrongpassword"}
        )
        print(f"\n=== LOGIN WITH INVALID CREDENTIALS ===")
        print(f"Status Code: {response.status_code}")
        try:
            data = response.json()
            pprint(data)
            
            # Extract error details from the 'detail' field
            error = data.get('detail', {})
            
            # Verify error structure
            assert "code" in error, "Error response should have 'code' field"
            assert "message" in error, "Error response should have 'message' field"
            
            print(f"✅ Error code: {error['code']}")
            print(f"✅ Error message: {error['message']}")
            
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            print(f"Raw response: {response.text}")

async def test_verify_otp_invalid_code():
    """Test OTP verification with an invalid code"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/submit-otp",
            json={
                "otp_code": "000000",  # Invalid OTP code
                "continuation_token": "fake-token"
            }
        )
        print(f"\n=== VERIFY OTP WITH INVALID CODE ===")
        print(f"Status Code: {response.status_code}")
        try:
            data = response.json()
            pprint(data)
            
            # Extract error details from the 'detail' field
            error = data.get('detail', {})
            
            # Verify error structure
            assert "code" in error, "Error response should have 'code' field"
            assert "message" in error, "Error response should have 'message' field"
            
            print(f"✅ Error code: {error['code']}")
            print(f"✅ Error message: {error['message']}")
            
            # Check for suberror if present
            if "suberror" in error:
                suberror = error["suberror"]
                assert "code" in suberror, "Suberror should have 'code' field"
                assert "message" in suberror, "Suberror should have 'message' field"
                print(f"✅ Suberror code: {suberror['code']}")
                print(f"✅ Suberror message: {suberror['message']}")
            
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            print(f"Raw response: {response.text}")

async def test_password_reset_invalid_email():
    """Test password reset with an invalid email"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/password-reset",
            json={"email": "nonexistent@example.com"}
        )
        print(f"\n=== PASSWORD RESET WITH INVALID EMAIL ===")
        print(f"Status Code: {response.status_code}")
        try:
            data = response.json()
            pprint(data)
            
            # Extract error details from the 'detail' field
            error = data.get('detail', {})
            
            # Verify error structure
            assert "code" in error, "Error response should have 'code' field"
            assert "message" in error, "Error response should have 'message' field"
            
            print(f"✅ Error code: {error['code']}")
            print(f"✅ Error message: {error['message']}")
            print(f"✅ Error context: {error.get('context', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            print(f"Raw response: {response.text}")

async def test_login_weak_password():
    """Test login with a weak password to check suberror handling"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "test@example.com", "password": "short"}
        )
        print(f"\n=== LOGIN WITH WEAK PASSWORD ===")
        print(f"Status Code: {response.status_code}")
        try:
            # This will likely fail if there's no user, but we can still check the error format
            data = response.json()
            pprint(data)
            
            # Extract error details from the 'detail' field
            error = data.get('detail', {})
            
            if "code" in error:
                print(f"✅ Error code: {error['code']}")
                print(f"✅ Error message: {error['message']}")
            else:
                print("❌ Expected error structure not found")
            
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            print(f"Raw response: {response.text}")

async def main():
    print("Starting Authentication Error Handling Tests")
    print("=" * 50)
    
    # Run the tests
    await test_login_invalid_credentials()
    await test_verify_otp_invalid_code()
    await test_password_reset_invalid_email()
    await test_login_weak_password()
    
    print("\n" + "=" * 50)
    print("Tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
