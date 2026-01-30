// index.js (cleaned + fixed)

const express = require('express');
const app = express();
const http = require('http');
const { PythonShell } = require('python-shell');
const fs = require('fs');

// Serve static files (index.html, xterm.css, xterm.js, etc.)
app.use(express.static('static'));

// Serve index.html on root URL
app.get('/', (req, res) => {
    res.sendFile(__dirname + '/static/index.html');
});

const server = http.createServer(app);
const io = require('socket.io')(server);

io.on('connection', (socket) => {
    console.log('Socket Connected');

    let pyshell = null;  // single instance per socket

    function startPython() {
        try {
            pyshell = new PythonShell('banking.py', {
                mode: 'text',
                pythonOptions: ['-u'],  // unbuffered output (critical!)
                env: { PYTHONUNBUFFERED: '1' }
            });

            console.log('Python shell started');

            // Force initial flush by sending newline after small delay
            setTimeout(() => {
                if (pyshell) {
                    pyshell.send('\n');
                    console.log('Sent initial newline to trigger Python flush');
                }
            }, 1000);  // 1 second delay to let script initialize

            socket.on('disconnect', () => {
                console.log('Socket Disconnected');
                if (pyshell) {
                    try { pyshell.end(); } catch (e) {}
                }
            });

            socket.on('command_entered', (command) => {
                if (pyshell) {
                    console.log('Socket Command:', command);
                    try { pyshell.send(command); } catch (e) {}
                }
            });

            pyshell.on('message', (message) => {
                console.log('Python stdout:', message);
                try { socket.emit('console_output', message); } catch (e) {}
            });

            pyshell.on('close', () => {
                console.log('Python process ended');
                socket.emit('console_output', '\r\n[Python process ended]');
            });

            pyshell.on('error', (err) => {
                console.error('Python error:', err);
                try { socket.emit('console_output', 'Python error: ' + err.message); } catch (e) {}
            });

            pyshell.on('pythonError', (message) => {
                console.error('Python STDERR:', message);
                socket.emit('console_output', '[Python Error] ' + message);
            });
        } catch (e) {
            console.error('Failed to start Python:', e);
            socket.emit('console_output', 'Failed to start Python: ' + e.message);
        }
    }

    // Handle creds and start Python
    if (process.env.CREDS) {
        fs.writeFile('creds.json', process.env.CREDS, 'utf8', (err) => {
            if (err) {
                console.log('Error writing creds.json:', err);
                socket.emit('console_output', 'Error saving creds: ' + err.message);
            } else {
                console.log('creds.json written successfully');
                startPython();
            }
        });
    } else {
        console.log('No CREDS env var – starting Python without creds file');
        startPython();
    }
});

const port = process.env.PORT || 3000;
server.listen(port, () => {
    console.log(`Server listening on port ${port}`);
});