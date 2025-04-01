# Reference Guide for Authentication API Error Codes

This document provides a comprehensive reference of all possible error codes that can be returned by the Authentication API. Errors are consistently structured to facilitate handling in the frontend.

## Error Structure

All error responses have the following structure:

```json
{
  "detail": {
    "code": "error_code",
    "message": "User-friendly message",
    "description": "Detailed technical description of the error",
    "context": "Context where the error occurred (endpoint/phase)",
    "suberror": {
      "code": "suberror_code",
      "message": "Specific suberror message"
    },
    "details": {
      // Additional information about the error
    }
  }
}
```

## Main Error Codes

| Code | HTTP Status | Description | Possible Contexts |
|--------|-------------|-------------|-------------------|
| `invalid_request` | 400 | Invalid request parameters or format | `/initiate`, `/challenge`, `/token`, register_user, verify_otp |
| `invalid_grant` | 400 | Authentication error (incorrect credentials) | `/token`, verify_otp, login, submit_otp |
| `expired_token` | 401 | The continuation token has expired | `/challenge`, `/token`, verify_otp |
| `attributes_required` | 400 | Additional user attributes are required | register_user |
| `unauthorized_client` | 401 | The application is not authorized | `/initiate`, `/token` |
| `unsupported_challenge_type` | 400 | Unsupported authentication method | `/challenge` |
| `user_not_found` | 404 | The user account does not exist | `/initiate`, password_reset_initiate |
| `invalid_client` | 401 | Error in the application configuration | `/initiate`, `/token` |

## Sub-errors

### For `invalid_grant`

| Code | Description |
|--------|-------------|
| `password_too_weak` | The password is too weak and does not meet complexity requirements |
| `password_too_short` | The password must be at least 8 characters long |
| `password_too_long` | The password exceeds the maximum of 256 characters |
| `password_recently_used` | The password has been used recently, please choose another one |
| `password_banned` | The password contains banned words or patterns |
| `password_is_invalid` | The password contains invalid characters |
| `invalid_oob_value` | The verification code is incorrect |
| `attribute_validation_failed` | Some of the provided data is not valid |

### For `invalid_client`

| Code | Description |
|--------|-------------|
| `nativeauthapi_disabled` | Native authentication is not enabled for this application |

## Errors by Endpoint

### User Registration (`/auth/register`)

| Code | Suberror | Description |
|--------|----------|-------------|
| `invalid_request` | - | Invalid parameters in the request |
| `attributes_required` | - | Required user attributes are missing |
| `invalid_grant` | `attribute_validation_failed` | Attribute validation failed |

### OTP Verification (`/auth/verify-otp` and `/auth/submit-otp`)

| Code | Suberror | Description |
|--------|----------|-------------|
| `invalid_grant` | `invalid_oob_value` | Incorrect OTP code |
| `expired_token` | - | The verification token has expired |

### Login (`/auth/login`)

| Code | Suberror | Description |
|--------|----------|-------------|
| `user_not_found` | - | User not found |
| `invalid_grant` | - | Incorrect credentials |
| `invalid_grant` | `password_is_invalid` | Invalid password |

### Password Reset (`/auth/password-reset`)

| Code | Suberror | Description |
|--------|----------|-------------|
| `user_not_found` | - | The email does not correspond to an existing user |
| `redirect_required` | - | Password reset requires browser-based flow |

### Password Reset Verification (`/auth/password-reset/verify`)

| Code | Suberror | Description |
|--------|----------|-------------|
| `invalid_grant` | `invalid_oob_value` | Incorrect verification code |
| `invalid_grant` | `password_too_weak` | The password is too weak |
| `invalid_grant` | `password_too_short` | The password is too short |
| `invalid_grant` | `password_recently_used` | The password has been used recently |
| `expired_token` | - | The reset token has expired |
| `password_reset_failed` | - | Error in password reset |
| `password_reset_timeout` | - | Timeout during reset |

## Error Handling in the Frontend

### Example Code

```javascript
async function handleAuthRequest(url, data) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      const errorDetail = errorData.detail;
      
      // Handle errors based on the code
      switch (errorDetail.code) {
        case 'user_not_found':
          showError('The user does not exist. Would you like to register?');
          break;
        case 'invalid_grant':
          // Check for suberror types
          if (errorDetail.suberror && errorDetail.suberror.code === 'invalid_oob_value') {
            showError('The verification code is incorrect. Please try again.');
          } else if (errorDetail.suberror && errorDetail.suberror.code === 'password_too_weak') {
            showError('The password is too weak. It must contain letters, numbers, and special characters.');
          } else {
            showError('Incorrect credentials. Please check your email and password.');
          }
          break;
        case 'expired_token':
          showError('Your session has expired. Please start the process again.');
          break;
        default:
          showError(errorDetail.message || 'An error occurred during authentication.');
      }
      
      // Log the error for diagnosis
      console.error('Auth error:', errorDetail);
      
      return { error: errorDetail };
    }
    
    return await response.json();
  } catch (error) {
    showError('Connection error. Please try again later.');
    console.error('Network error:', error);
    return { error: { code: 'network_error', message: 'Connection error' } };
  }
}
```