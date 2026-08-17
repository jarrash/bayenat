# Bayenat authentication and authorization

## JWT contract

Bayenat accepts `Authorization: Bearer <token>` on REST routes. Tokens are signed with the configured JWT secret and issuer and contain `sub`, `tenant_id`, `role`, `email`, `iat`, and `exp` claims. The API rejects invalid, expired, wrongly issued, or structurally incomplete tokens.

The authenticated principal is resolved to a database user and tenant for database-backed routes. Every case, evidence item, processing job, and integrity lookup is filtered by the principal tenant. Cross-tenant resources return `404` rather than confirming that a resource exists.

## Development fallback

The development principal is enabled only when `BAYENAT_ENVIRONMENT` is `development` or `test` and `BAYENAT_ALLOW_DEV_PRINCIPAL=true`. Set `BAYENAT_ALLOW_DEV_PRINCIPAL=false` in any shared or production environment. WebSocket event and stream routes accept the bearer token in the handshake `Authorization` header or the `access_token` query parameter for clients that cannot set headers; prefer the header because query strings can be logged.

## Rate limiting

REST requests are limited by client IP using a bounded in-memory sliding window. WebSocket handshakes use a separate limit by client IP. `Retry-After` is returned for REST `429` responses, and rejected WebSocket handshakes close with code `1008`. This local limiter is a safety boundary, not a distributed production quota system; production deployments should use Redis-backed counters keyed by tenant and authenticated subject, with trusted proxy handling and route-specific costs.

## Configuration

```bash
BAYENAT_JWT_SECRET=use-a-random-secret
BAYENAT_JWT_ISSUER=bayenat-api
BAYENAT_ALLOW_DEV_PRINCIPAL=false
BAYENAT_RATE_LIMIT_REQUESTS=120
BAYENAT_RATE_LIMIT_WINDOW_SECONDS=60
BAYENAT_WEBSOCKET_RATE_LIMIT_REQUESTS=30
BAYENAT_WEBSOCKET_RATE_LIMIT_WINDOW_SECONDS=60
```

## Remaining production controls

Before processing real evidence, add refresh-token rotation or an external identity provider, key rotation with a key ID, durable Redis rate limiting, trusted proxy configuration, audit events for authentication failures and authorization denials, stream ownership persistence, maximum WebSocket frame sizes, body-size limits, and worker-side reauthorization before reading private storage.
