# QuantEngine ↔ trading-app Protocol (v1)

This document defines the v1 control-plane envelope for reliable order submission and cancel/replace via ZeroMQ.

## Envelope
- Transport: ZeroMQ PUSH (sender) → PULL (trading-app)
- ACKs: ZeroMQ PUB (trading-app) → SUB (sender), topic: `order_acks`
- Serialization: JSON (intermediate); protobuf planned (`shared_proto/envelope.proto`)

Fields:
- version: string ("v1")
- correlation_id: string (opaque; used for retries/acks)
- msg_type: string ("SimpleOrder" | "CancelReplaceRequest")
- payload: object (message-specific)

Example SimpleOrder:
```
{
  "version": "v1",
  "correlation_id": "abc-123",
  "msg_type": "SimpleOrder",
  "payload": {
    "symbol": "AAPL",
    "action": "BUY",
    "qty": 10,
    "order_type": "MKT",
    "limit_price": 0.0
  }
}
```

ACK example:
```
{
  "version": "v1",
  "kind": "Ack",
  "correlation_id": "abc-123",
  "status": "ACCEPTED", // or REJECT
  "reason": "",
  "order_id": 1001 // when available
}
```

## Validation and Risk Guards
- ALLOWED_SYMBOLS: optional whitelist
- MAX_QTY / MAX_NOTIONAL / MIN_PRICE / MAX_PRICE
- TRADING_HOURS in MARKET_TZ (default 0930–1600 America/New_York)

## Addresses (defaults)
- Inbound v1: `V1_ZMQ_ADDR=tcp://127.0.0.1:5556`
- ACK PUB: `V1_ACK_PUB_ADDR=tcp://127.0.0.1:6003` (topic `order_acks`)
- HWM: `ZMQ_RCVHWM=10000`, `ZMQ_SNDHWM=10000`

## Migration plan
1. Use `scripts/v1_receiver.py` alongside existing listeners.
2. Migrate senders to send v1 envelope JSON.
3. Switch ACK consumers to `order_acks` topic.
4. Generate protobufs from `shared_proto/envelope.proto` and update both sides to protobuf.

## Retries
- Sender publishes envelope with correlation_id.
- If no ACK within timeout, retry with backoff (idempotent on gateway side for CR via sqlite mapping; SimpleOrder currently non-idempotent).
- Future: add idempotency key for SimpleOrder and persist mapping.
