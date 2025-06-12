import zmq
import cr_pb2  # This is your generated Python protobuf class
from core import TradingApp, create_contract, create_order
import logging


# Setup ZeroMQ PULL socket
context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5555")  # Match the endpoint from C++ sender

print("Python ZMQ receiver listening on tcp://*:5555...")

while True:
    msg = socket.recv()
    req = cr_pb2.CancelReplaceRequest()
    if req.ParseFromString(msg):
        print(f"Received CancelReplaceRequest: order_id={req.order_id}, price={req.params.new_price}, qty={req.params.new_qty}")
        # Here, interface with IBKR
        # Example: call your update_order logic
        app = TradingApp(account="YOUR_ACCOUNT_ID")  # Provide proper account
        contract = create_contract("AAPL")           # You might want this symbol in your proto in future!
        order = create_order("BUY", "LMT", req.params.new_qty, limit_price=req.params.new_price, account="YOUR_ACCOUNT_ID")
        app.update_order(contract, order, req.order_id)
        print("Order update triggered in IBKR.")
    else:
        print("Failed to parse CancelReplaceRequest protobuf")

