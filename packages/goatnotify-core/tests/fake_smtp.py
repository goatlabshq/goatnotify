import asyncio
from dataclasses import dataclass, field


@dataclass
class FakeSmtpServer:
    replies: dict[str, str] = field(default_factory=dict[str, str])
    commands: list[str] = field(default_factory=list[str])
    messages: list[bytes] = field(default_factory=list[bytes])
    port: int = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 fake ESMTP\r\n")
        while line := await reader.readline():
            command = line.decode().strip()
            verb = command.split(" ", 1)[0].upper()
            self.commands.append(command)
            if verb in self.replies:
                writer.write(f"{self.replies[verb]}\r\n".encode())
            elif verb == "DATA":
                writer.write(b"354 go ahead\r\n")
                await writer.drain()
                self.messages.append(await reader.readuntil(b"\r\n.\r\n"))
                writer.write(b"250 queued\r\n")
            elif verb == "QUIT":
                writer.write(b"221 bye\r\n")
                await writer.drain()
                writer.close()
                return
            else:
                writer.write(b"250 ok\r\n")
            await writer.drain()
