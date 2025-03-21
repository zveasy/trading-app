from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class PositionApp(EClient, EWrapper):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)  # ✅ Pass self to EClient

    def position(self, account, contract, position, avgCost):
        if position != 0:
            print(f"\n📊 Position:")
            print(f"  Symbol   : {contract.symbol}")
            print(f"  Quantity : {position}")
            print(f"  Avg Cost : {avgCost}")

    def positionEnd(self):
        print("\n✅ Done retrieving positions.")
        self.disconnect()

app = PositionApp()
app.connect("127.0.0.1", 7497, clientId=0)
app.reqPositions()
app.run()
