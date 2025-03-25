# wrapper.py
from ibapi.wrapper import EWrapper

class IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self.nextValidOrderId = None
        self.positions = []
        self.portfolio = []

    def nextValidId(self, orderId: int):
        self.nextValidOrderId = orderId

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"OrderStatus - ID:{orderId}, Status:{status}, Filled:{filled}, Remaining:{remaining}, Last Fill Price:{lastFillPrice}")

    def openOrder(self, orderId, contract, order, orderState):
        print(f"OpenOrder - ID:{orderId}, {contract.symbol}, {order.action}, {order.totalQuantity}, Status:{orderState.status}")

    def execDetails(self, reqId, contract, execution):
        print(f"ExecDetails - {contract.symbol}, {execution.side}, {execution.shares}, Price:{execution.price}")

    def position(self, account, contract, position, avgCost):
        self.positions.append((account, contract.symbol, position, avgCost))

    def positionEnd(self):
        print("✅ Positions fetched successfully.")

    def updatePortfolio(self, contract, position, marketPrice, marketValue,
                        averageCost, unrealizedPNL, realizedPNL, accountName):
        self.portfolio.append((contract.symbol, position, marketPrice, marketValue,
                               averageCost, unrealizedPNL, realizedPNL))

    def accountSummary(self, reqId, account, tag, value, currency):
        print(f"AccountSummary - {tag}: {value} {currency}")
