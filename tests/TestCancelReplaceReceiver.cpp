// tests/TestCancelReplaceReceiver.cpp
#include "gen/cpp/cr.pb.h"
#include <zmq.hpp>
#include <iostream>
#include <thread>

int main() {
    zmq::context_t context(1);
    zmq::socket_t socket(context, zmq::socket_type::pull);

    // Bind to the same endpoint used by CommGateway sender
    socket.bind("tcp://*:5555");

    std::cout << "Receiver is listening on tcp://*:5555..." << std::endl;

    zmq::message_t msg;
    while (true) {
        if (!socket.recv(msg, zmq::recv_flags::none))
            continue;

        // Parse as CancelReplaceRequest Protobuf
        cr::CancelReplaceRequest req;
        if (req.ParseFromArray(msg.data(), static_cast<int>(msg.size()))) {
            std::cout << "Received CancelReplaceRequest:" << std::endl;
            std::cout << "  order_id: " << req.order_id() << std::endl;
            std::cout << "  new_price: " << req.params().new_price() << std::endl;
            std::cout << "  new_qty: " << req.params().new_qty() << std::endl;
            std::cout << "  ts_ns: " << req.ts_ns() << std::endl;
        } else {
            std::cout << "Failed to parse CancelReplaceRequest protobuf!" << std::endl;
        }
    }
    return 0;
}

