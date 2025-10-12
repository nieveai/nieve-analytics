const { EventEmitter } = require('events');

const messageQueue = [];

class MockSocket extends EventEmitter {
    constructor() {
        super();
        this.connect = jest.fn();
        this.send = jest.fn(() => {
            return Promise.resolve();
        });
        this.close = jest.fn();
    }

    async *[Symbol.asyncIterator]() {
        while (true) {
            if (messageQueue.length > 0) {
                yield [Buffer.from(messageQueue.shift())];
            }
            await new Promise(resolve => setImmediate(resolve));
        }
    }
}

const zmq = {
    Request: MockSocket,
    __pushSocketMessage: (msg) => {
        messageQueue.push(JSON.stringify(msg));
    },
    __pushRawSocketMessage: (msg) => {
        messageQueue.push(msg);
    },
    __clearSocketMessages: () => {
        messageQueue.length = 0;
    }
};

module.exports = zmq;
