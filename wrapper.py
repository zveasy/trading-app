from ibapi.wrapper import EWrapper

class IBWrapper(EWrapper):
    def __init__(self):
        EWrapper.__init__(self)

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error ({errorCode}): {errorString}")
