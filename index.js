const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { PythonShell } = require('python-shell');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

/* Serve static files */
app.use(express.static('static'));

io.on('connection', (socket) => {
    console.log("Socket Connected");

    let pyshell;

    function run_python_script() {
        try {
            pyshell = new PythonShell('banking.py');

            pyshell.on('message', (message) => {
                console.log('process Out:', message);
                socket.emit("console_output", message);
            });

            pyshell.on('error', (err) => {
                console.log('Process error:', err);
                socket.emit("console_output", String(err));
            });

            pyshell.on('close', () => {
                console.log('Process ended');
            });

        } catch (e) {
            console.error("Exception running python", e);
        }
    }

    socket.on('command_entered', (command) => {
        if (!pyshell) return;
        console.log("Socket Command:", command);
        pyshell.send(command);
    });

    socket.on('disconnect', () => {
        console.log("Socket Disconnected");
        if (pyshell) pyshell.kill();
    });

    if (process.env.CREDS) {
        fs.writeFile('creds.json', process.env.CREDS, 'utf8', (err) => {
            if (err) {
                socket.emit("console_output", "Error saving credentials");
            } else {
                run_python_script();
            }
        });
    } else {
        run_python_script();
    }
});

server.listen(PORT, () => {
    console.log('Server running on port', PORT);
});
