get_dl_url(){ 
    version_url="https://dist.torproject.org/torbrowser/?C=M;O=D"
    version="$(curl -s "$version_url" | grep -m 1 -Po "(?<=>)\d+.\d+(.\d+)?(?=/)")"
    echo "https://www.torproject.org/dist/torbrowser/${version}/tor-browser-linux-x86_64-${version}.tar.xz" 
}

get_dl_url