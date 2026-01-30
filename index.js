const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const { PythonShell } = require("python-shell");
const fs = require("fs");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 8000;

/* Serve static files */
app.use(express.static("static"));

function writeCredsIfNeeded() {
    if (process.env.CREDS) {
        fs.writeFileSync("creds.json", process.env.CREDS);
        console.log("✅ creds.json written from CREDS");
    } else {
        console.error("❌ CREDS env var not found");
    }
}

io.on("connection", (socket) => {
    console.log("Socket Connected");

    let pyshell;

    function run_python_script() {
        writeCredsIfNeeded();   // 🔑 MUST happen first

        pyshell = new PythonShell("banking.py");

        pyshell.on("message", (message) => {
            socket.emit("console_output", message);
        });

        pyshell.on("error", (err) => {
            socket.emit("console_output", String(err));
        });

        socket.on("command_entered", (command) => {
            pyshell.send(command);
        });

        socket.on("disconnect", () => {
            if (pyshell) pyshell.kill();
        });
    }

    run_python_script();
});

server.listen(PORT, () => {
    console.log("Server running on port", PORT);
});
