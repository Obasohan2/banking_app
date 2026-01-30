// index.js (updated)

const express = require('express');
const app = express();
const http = require('http');
const { PythonShell } = require('python-shell');
const fs = require('fs');

// Serve static files from ./static (index.html, xterm.js, xterm.css, etc.)
app.use(express.static('static'));

const server = http.createServer(app);
const io = require('socket.io')(server);

io.on('connection', (socket) => {
    console.log("Socket Connected");

    function run_python_script() {
        try {
            let pyshell = new PythonShell('banking.py');  // your Python file

            socket.on('disconnect', () => {
                console.log("Socket Disconnected");
                try { pyshell.kill(); } catch (e) {}
            });

            socket.on('command_entered', (command) => {
                console.log("Socket Command:", command);
                try { pyshell.send(command); } catch (e) {}
            });

            pyshell.on('message', (message) => {
                console.log('Python stdout:', message);
                try { socket.emit("console_output", message); } catch (e) {}
            });

            pyshell.on('close', () => {
                console.log('Python process ended');
            });

            pyshell.on('error', (err) => {
                console.log('Python error:', err);
                try { socket.emit("console_output", "Python error: " + err.message); } catch (e) {}
            });
        } catch (e) {
            console.error("Failed to start Python:", e);
            socket.emit("console_output", "Failed to start Python: " + e.message);
        }
    }

    if (process.env.CREDS) {
        fs.writeFile('creds.json', process.env.CREDS, 'utf8', (err) => {
            if (err) {
                console.log('Error writing creds.json:', err);
                socket.emit("console_output", "Error saving creds: " + err.message);
            } else {
                run_python_script();
            }
        });
    } else {
        run_python_script();
    }
});

const port = process.env.PORT || 3000;
server.listen(port, () => {
    console.log(`Server listening on port ${port}`);
});