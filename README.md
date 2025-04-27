# vibeworld

![](thumbnail.gif)

1. Install Three.js
2. Launch vite
3. Go to http://localhost:5173/
4. Launch the Trellis server
    1. `ssh` to a remote machine with a GPU
    2. launch the server (and install any dependencies)
    
    ```bash
    python -m trellis_server --host 0.0.0.0 --port 8000 --preload-models
    ```

    3. Then you need to tunnel the port to your laptop. Leave this command running in a local terminal.

    ```bash
    ssh -L 8000:localhost:8000 username@remote-hostname
    ```
5. Run the websocket server: `python websocket_server.py`

Built with
- Claude
- Three js
- Eleven Labs
- Trellis (via PyTorch)


