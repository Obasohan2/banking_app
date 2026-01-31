const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const { PythonShell } = require("python-shell");
const fs = require("fs");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 8000;

// Serve frontend
app.use(express.static("static"));

function writeCreds() {
    if (process.env.CREDS) {
        fs.writeFileSync("creds.json", process.env.CREDS);
        console.log("creds.json written from CREDS");
    } else {
        console.log("CREDS env var not set");
    }
}

io.on("connection", (socket) => {
    console.log("Socket connected");

    writeCreds();

    const pyshell = new PythonShell("banking.py", {
        pythonOptions: ["-u"] // unbuffered output ONLY
    });

    // Python stdout → browser terminal
    pyshell.on("message", (message) => {
        socket.emit("console_output", message);
    });

    // Python errors → browser terminal
    pyshell.on("stderr", (stderr) => {
        socket.emit("console_output", stderr);
    });

    pyshell.on("error", (err) => {
        socket.emit("console_output", `Python error: ${err}`);
    });

    // Browser input → Python stdin
    socket.on("command_entered", (command) => {
        pyshell.send(command);
    });

    socket.on("disconnect", () => {
        console.log("Socket disconnected");
        pyshell.kill();
    });
});

server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
