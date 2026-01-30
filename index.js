const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const { PythonShell } = require("python-shell");
const fs = require("fs");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 8000;

app.use(express.static("static"));

function writeCreds() {
    if (process.env.CREDS) {
        fs.writeFileSync("creds.json", process.env.CREDS);
        console.log("✅ creds.json written from CREDS");
    }
}

io.on("connection", (socket) => {
    console.log("Socket Connected");

    writeCreds();

    const pyshell = new PythonShell("banking.py", {
        pythonOptions: ["-u"],
        stdio: ["pipe", "pipe", "pipe"]
    });

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
        console.log("🔌 Socket disconnected");
        pyshell.kill();
    });

    // 🔥 Kickstart Python input()
    setTimeout(() => {
        pyshell.send("");
    }, 200);
});

server.listen(PORT, () => {
    console.log("🚀 Server running on port", PORT);
});
