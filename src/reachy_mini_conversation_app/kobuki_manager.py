"""Kobuki mobile base WebSocket manager.

This module provides a WebSocket client to send command strings to a Kobuki mobile base robot
via a WebSocket server.
"""

import asyncio
import logging
import argparse
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosedError, InvalidURI


logger = logging.getLogger(__name__)


class KobukiManager:
    """WebSocket manager for sending commands to Kobuki mobile base."""

    def __init__(self, websocket_url: str, timeout: float = 5.0):
        """Initialize the Kobuki manager.

        Args:
            websocket_url: WebSocket server URL (e.g., "ws://localhost:8080/kobuki")
            timeout: Connection timeout in seconds
        """
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False

    async def connect(self) -> None:
        """Establish WebSocket connection to the server."""
        if self._connected:
            logger.warning("Already connected to WebSocket server")
            return

        try:
            logger.info(f"Connecting to Kobuki WebSocket server at {self.websocket_url}")
            self.websocket = await websockets.connect(
                self.websocket_url,
                ping_interval=None,  # Disable ping/pong for simplicity
                close_timeout=self.timeout,
            )
            self._connected = True
            logger.info("Successfully connected to Kobuki WebSocket server")
        except InvalidURI as e:
            logger.error(f"Invalid WebSocket URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server: {e}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if not self._connected or not self.websocket:
            return

        try:
            await self.websocket.close()
            logger.info("Disconnected from Kobuki WebSocket server")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
        finally:
            self._connected = False
            self.websocket = None

    async def send_command(self, command: str) -> Optional[str]:
        """Send a command string to the Kobuki server.

        Args:
            command: Command string to send

        Returns:
            Response message from server, or None if no response
        """
        if not self._connected or not self.websocket:
            raise RuntimeError("Not connected to WebSocket server. Call connect() first.")

        try:
            logger.debug(f"Sending command: {command}")
            await self.websocket.send(command)

            # Try to receive a response (with timeout)
            try:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                logger.debug(f"Received response: {response}")
                return response
            except asyncio.TimeoutError:
                # No response received, which is fine for fire-and-forget commands
                logger.debug("No response received (timeout)")
                return None
        except ConnectionClosedError as e:
            logger.error(f"WebSocket connection closed: {e}")
            self._connected = False
            raise
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        """Check if connected to WebSocket server."""
        return self._connected


async def main() -> None:
    """Command-line interface for sending commands to Kobuki mobile base."""
    parser = argparse.ArgumentParser(
        description="Send commands to Kobuki mobile base via WebSocket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send a command string
  python -m reachy_mini_conversation_app.kobuki_manager --url ws://localhost:8080/kobuki "forward"
  
  # Send any command string
  python -m reachy_mini_conversation_app.kobuki_manager "stop"
  
  # Keep connection open for 5 seconds
  python -m reachy_mini_conversation_app.kobuki_manager "forward" --duration 5.0
        """,
    )
    parser.add_argument(
        "command",
        type=str,
        help="Command string to send to the WebSocket server",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="ws://localhost:8080/kobuki",
        help="WebSocket server URL (default: ws://localhost:8080/kobuki)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Connection timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Duration to keep connection open in seconds (default: 0.0, disconnect immediately)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create manager and connect
    manager = KobukiManager(args.url, timeout=args.timeout)

    try:
        await manager.connect()

        # Send the command string directly
        response = await manager.send_command(args.command)

        if response:
            print(f"Server response: {response}")

        # Keep connection open for specified duration
        if args.duration > 0.0:
            print(f"Keeping connection open for {args.duration} seconds...")
            await asyncio.sleep(args.duration)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1
    finally:
        await manager.disconnect()

    return 0


def cli_main() -> None:
    """Synchronous entry point for console script."""
    exit(asyncio.run(main()))


if __name__ == "__main__":
    cli_main()

