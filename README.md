# carGPT

## Environment setup

1. Activate poetry environment by:

    ```shell
    poetry shell
    ```

2. Install all necessary packages by:

    ```shell
    poetry install
    ```

## Njuskalo scraper

1. Install tor

2. Install `npm`

    ```bash
    sudo apt install npm
    ```

3. Install `http-proxy-to-socks`

    ```bash
    sudo npm install -g http-proxy-to-socks
    ```

4. Run `hpts`

    ```bash
    hpts -s 127.0.0.1:9050 -p 8080
    ```

    Where `9050` is the sock port which tor uses.

5. Run