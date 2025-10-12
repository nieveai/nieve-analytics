const zmq = require('zeromq');

async function run() {
  console.log('ZeroMQ version:', zmq.version);
  const sock = new zmq.Request();
  sock.connect('tcp://127.0.0.1:5555');

  try {
    await sock.send("test");
    console.log("message sent");
    
  } catch (err) {
    console.error('An error occurred with the ZeroMQ module:', err);
  }
}

run();
