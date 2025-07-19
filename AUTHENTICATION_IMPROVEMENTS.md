# Authentication System Improvements

## Overview

This document outlines the comprehensive improvements made to the Krypton authentication system, addressing security concerns and implementing modern authentication best practices.

## Key Improvements

### 1. **JWT Token Management**
- **Access Tokens**: Short-lived (30 minutes) for API requests
- **Refresh Tokens**: Long-lived (7 days) for token renewal
- **Automatic Token Refresh**: Seamless token renewal without user intervention
- **Token Validation**: Server-side verification of token authenticity

### 2. **Enhanced Security**
- **Rate Limiting**: 60 requests per minute per IP address
- **CORS Configuration**: Restricted to specific origins
- **Secure Session Management**: Proper session secret handling
- **Input Validation**: Comprehensive request validation
- **Error Handling**: Secure error responses without information leakage

### 3. **Improved User Experience**
- **Automatic Authentication**: Persistent login across browser sessions
- **Graceful Token Expiry**: Automatic logout and redirect on token expiration
- **Loading States**: Better user feedback during authentication processes
- **Error Recovery**: Clear error messages and recovery options

## Architecture

### Backend Authentication Flow

```
1. User clicks "Login with Google"
2. Firebase Auth handles Google OAuth
3. Frontend sends Firebase ID token to backend
4. Backend verifies Firebase token
5. Backend creates/retrieves user from database
6. Backend creates/retrieves user wallet
7. Backend generates JWT access and refresh tokens
8. Frontend stores tokens securely
9. Frontend redirects to wallet page
```

### Token Refresh Flow

```
1. API request made with access token
2. If token expired, 401 response received
3. Frontend automatically attempts token refresh
4. If refresh successful, retry original request
5. If refresh failed, redirect to login
```

## API Endpoints

### Authentication Endpoints

#### `POST /api/v1/auth/login`
- **Purpose**: Authenticate user with Firebase token
- **Request**: `{ "idToken": "firebase_id_token" }`
- **Response**: User data + JWT tokens
- **Rate Limit**: 10 requests per minute

#### `POST /api/v1/auth/refresh`
- **Purpose**: Refresh access token using refresh token
- **Request**: `{ "refresh_token": "jwt_refresh_token" }`
- **Response**: New access and refresh tokens
- **Rate Limit**: 30 requests per minute

#### `POST /api/v1/auth/logout`
- **Purpose**: Logout user (client-side token cleanup)
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: Success message
- **Rate Limit**: 10 requests per minute

#### `GET /api/v1/auth/me`
- **Purpose**: Get current user profile
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: User profile data
- **Rate Limit**: 60 requests per minute

#### `POST /api/v1/auth/verify-token`
- **Purpose**: Verify if access token is valid
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: Token validity status
- **Rate Limit**: 60 requests per minute

## Frontend Implementation

### AuthManager Class

The `AuthManager` class provides a centralized authentication interface:

```typescript
// Token management
authManager.setTokens(tokens)
authManager.getAccessToken()
authManager.isAuthenticated()
authManager.logout()

// Automatic token refresh
authManager.getValidToken()
authManager.refreshAccessToken()
```

### API Client Integration

The API client automatically handles authentication:

```typescript
// Automatic token inclusion in requests
api.get('/api/v1/protected-endpoint')

// Automatic token refresh on 401 errors
api.post('/api/v1/auth/refresh', { refresh_token })
```

### Protected Routes

Components automatically check authentication status:

```typescript
useEffect(() => {
  if (!authManager.isAuthenticated()) {
    router.push('/');
    return;
  }
  // Load protected content
}, []);
```

## Security Features

### 1. **Token Security**
- JWT tokens signed with strong secret key
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Token type validation prevents misuse

### 2. **Rate Limiting**
- Global rate limiting on all endpoints
- Stricter limits on authentication endpoints
- IP-based rate limiting prevents abuse

### 3. **CORS Protection**
- Restricted to specific origins
- Credentials support for secure requests
- Proper headers configuration

### 4. **Input Validation**
- Pydantic models for request validation
- Type checking and sanitization
- Comprehensive error handling

## Environment Variables

### Required Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Firebase Configuration
FIREBASE_PROJECT_ID=krypton-test-38298
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY=your-private-key
FIREBASE_CLIENT_EMAIL=your-client-email
FIREBASE_CLIENT_ID=your-client-id

# Security
SESSION_SECRET_KEY=your-super-secret-session-key-change-in-production
CORS_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

## Migration Guide

### From Old Authentication System

1. **Update Environment Variables**
   - Add JWT configuration
   - Update Firebase configuration
   - Set security variables

2. **Update Frontend**
   - Install new dependencies: `npm install jwt-decode`
   - Replace old authentication logic with AuthManager
   - Update API calls to use new endpoints

3. **Update Backend**
   - Install new dependencies: `pip install python-jose[cryptography] passlib[bcrypt] python-multipart slowapi`
   - Update API routes to use new authentication
   - Add rate limiting middleware

### Testing Authentication

1. **Login Flow**
   ```bash
   # Test login endpoint
   curl -X POST /api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"idToken": "firebase_id_token"}'
   ```

2. **Token Refresh**
   ```bash
   # Test token refresh
   curl -X POST /api/v1/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "jwt_refresh_token"}'
   ```

3. **Protected Endpoint**
   ```bash
   # Test protected endpoint
   curl -X GET /api/v1/auth/me \
     -H "Authorization: Bearer access_token"
   ```

## Best Practices

### 1. **Token Storage**
- Store tokens in localStorage (for web apps)
- Never store tokens in URL parameters
- Clear tokens on logout

### 2. **Error Handling**
- Handle 401 errors gracefully
- Implement automatic token refresh
- Provide clear error messages

### 3. **Security**
- Use HTTPS in production
- Rotate JWT secrets regularly
- Monitor for suspicious activity

### 4. **Performance**
- Implement token caching
- Use efficient token validation
- Minimize API calls

## Troubleshooting

### Common Issues

1. **Token Expired**
   - Check token expiration time
   - Verify refresh token is valid
   - Clear localStorage and re-login

2. **CORS Errors**
   - Verify CORS_ORIGINS configuration
   - Check frontend URL matches allowed origins
   - Ensure credentials are included

3. **Rate Limiting**
   - Check rate limit configuration
   - Implement exponential backoff
   - Monitor API usage

4. **Firebase Issues**
   - Verify Firebase configuration
   - Check Firebase project settings
   - Ensure Firebase Admin SDK is initialized

## Future Enhancements

### Planned Improvements

1. **Multi-Factor Authentication**
   - SMS/Email verification
   - Hardware security keys
   - Biometric authentication

2. **Advanced Security**
   - Device fingerprinting
   - Anomaly detection
   - IP whitelisting

3. **User Management**
   - Role-based access control
   - Permission management
   - User activity logging

4. **Performance Optimization**
   - Token caching strategies
   - Database query optimization
   - CDN integration

## Support

For authentication-related issues:

1. Check the logs for detailed error messages
2. Verify environment variable configuration
3. Test with the provided curl commands
4. Review the troubleshooting section
5. Contact the development team

---

*This authentication system provides enterprise-grade security while maintaining excellent user experience.* 