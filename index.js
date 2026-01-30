const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { PythonShell } = require('python-shell');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

/* Serve static files */
app.use(express.static(path.join(__dirname, 'static')));

io.on('connection', (socket) => {
    console.log('✅ Socket connected');

    let pyshell = null;

    function run_python_script() {
        try {
            pyshell = new PythonShell('banking.py', {
                pythonOptions: ['-u'],       // 🔥 CRITICAL: unbuffered output
                mode: 'text',
                stdio: ['pipe', 'pipe', 'pipe']
            });

            pyshell.on('message', (message) => {
                socket.emit('console_output', message);
            });

            pyshell.on('stderr', (stderr) => {
                socket.emit('console_output', stderr);
            });

            pyshell.on('close', () => {
                socket.emit('console_output', '\n❌ Program exited');
                pyshell = null;
            });

        } catch (err) {
            console.error('❌ Python launch failed:', err);
            socket.emit('console_output', 'Python failed to start');
        }
    }

    socket.on('command_entered', (command) => {
        if (!pyshell) return;
        pyshell.send(command);
    });

    socket.on('disconnect', () => {
        console.log('🔌 Socket disconnected');
        if (pyshell) {
            pyshell.terminate();
            pyshell = null;
        }
    });

    /* Write creds.json from Heroku env */
    if (process.env.CREDS) {
        fs.writeFile('creds.json', process.env.CREDS, 'utf8', (err) => {
            if (err) {
                socket.emit('console_output', '❌ Failed to write creds.json');
            } else {
                run_python_script();
            }
        });
    } else {
        run_python_script();
    }
});

server.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
});
