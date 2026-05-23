# AEGIS Asset Recon  (20260523T081833Z)

Host: `cyberviser`  User: `x`  Mode: **Deep**
Output dir: `/home/x/aegis-model/recon/inventory/20260523T081833Z`

## Quick stats

| Metric | Value |
|---|---|
| Distro | Kali GNU/Linux Rolling |
| Kernel | 6.19.14+kali-amd64 |
| CPU cores | 16 |
| Memory total | 18.9 GB |
| Disk free (/) | 9.2G / 221G |
| Listening TCP ports | 87 |
| Running services | 36 |
| Docker containers (running) | 13 |
| Docker images | 15 |
| Ollama models | 10 |
| Git repos in /home/x | 5 |
| Live LAN hosts (192.168.0.0/24) | 9 |

## Network exposure (this host's listening ports)

```
0.0.0.0:22
0.0.0.0:2222
0.0.0.0:3000
0.0.0.0:3030
0.0.0.0:5000
0.0.0.0:5432
0.0.0.0:6379
0.0.0.0:7070
0.0.0.0:8080
0.0.0.0:9090
0.0.0.0:9091
10.0.3.1:53
10.0.3.1:53613
*:10250
10.42.0.1:43751
10.42.3.0:57313
10.42.3.1:52479
127.0.0.1:10010
127.0.0.1:10248
127.0.0.1:10249
127.0.0.1:10256
127.0.0.1:11434
127.0.0.1:37343
127.0.0.1:37477
127.0.0.1:38749
127.0.0.1:39837
127.0.0.1:43175
127.0.0.1:43209
127.0.0.1:6444
[::1]:34891
[::1]:45257
[::1]:6444
*:1716
172.17.0.1:34673
172.18.0.1:33163
172.19.0.1:43552
172.20.0.1:58183
172.21.0.1:57477
172.22.0.1:39716
192.168.0.83:42153
[::]:22
[::]:2222
[2600:8807:2680:7bc0:14ab:ff09:1c11:8786]:44588
[2600:8807:2680:7bc0::f340]:48913
[::]:3000
[::]:3030
*:3389
[::]:5000
[::]:5432
*:55966
[::]:6379
[::]:7070
[::]:8080
[::]:9090
[::]:9091
[fc42:5009:ba4b:5ab0::1]:39936
[fc42:5009:ba4b:5ab0::1]:53
[fe80::1c8a:42ff:fe92:36da]%vethcff2535:57219
[fe80::2884:87ff:fe71:ac57]%vethf290dc2:36112
[fe80::3052:caff:fed5:3aec]%vethbe463ad5:60243
[fe80::3cc7:60ff:fedc:6d33]%veth2461f4e:51109
[fe80::441:10ff:fe24:248]%vethb6d1c1b:56493
[fe80::58c7:f9ff:fe85:2318]%veth8fc61a2:56427
[fe80::60d2:5cff:fead:a244]%vethea9488e:51172
[fe80::60d7:75ff:fec2:e930]%vethedd121e:38412
[fe80::6448:f5ff:fe30:b62d]%vethabc0d4e:40344
[fe80::6852:51ff:fe1b:8ca9]%br-e2b2552c5fdd:39753
[fe80::6c0e:7ff:fed6:d71]%flannel.1:51898
[fe80::6c69:dbff:feab:9591]%veth564841b:37981
[fe80::74c4:7fff:fec9:423f]%vethc6d2131:49245
[fe80::7c24:ecff:fe5c:d1e6]%veth38a9c8c:38348
[fe80::7ce7:4bff:fe38:2d45]%vethad4461d:59333
[fe80::86f3:a58a:8e70:c77f]%wlan0:50482
[fe80::9458:47ff:fe09:2ae6]%vetha95f726:40899
[fe80::94e9:a4ff:fe99:dbdf]%br-f117c391d11b:45056
[fe80::9c15:73ff:fe61:bd56]%veth4d15958:58201
[fe80::9c22:efff:fe63:b2ba]%vethd13a1f7:58895
[fe80::a8cc:c7ff:fe3c:cd03]%veth8d900f9f:48265
[fe80::b498:7fff:fe49:1988]%br-b2522fb0e281:44985
[fe80::b8aa:d1ff:fe42:ecb1]%docker0:41345
[fe80::bc71:a9ff:fe03:6140]%br-f6379ced3668:43536
[fe80::cfb5:c3b6:35b3:3cc8]%eth0:43351
[fe80::d0eb:68ff:febf:2d27]%br-ea4509c52de0:37228
[fe80::e81f:e1ff:fe42:fc8d]%vethcb3fb98:33360
[fe80::e83c:f5ff:feb3:e957]%veth97b04b9:44005
[fe80::f0ce:44ff:fee0:62b6]%cni0:46094
[::ffff:127.0.0.1]:43451
```

## Live LAN hosts

```
192.168.0.1
192.168.0.121
192.168.0.162
192.168.0.189
192.168.0.192
192.168.0.193
192.168.0.210
192.168.0.37
192.168.0.83
```

### Discovered services

```
22/filtered/tcp//ssh///, 23/filtered/tcp//telnet///, 53/open/tcp//domain//dnsmasq 2.83/, 80/open/tcp//http?///, 111/filtered/tcp//rpcbind///, 443/open/tcp//ssl|https?///, 8080/filtered/tcp//http-proxy///, 49152/open/tcp//upnp//Portable SDK for UPnP devices 1.6.22 (Linux 4.9.314-cougarmountain; UPnP 1.0)/
22/open/tcp//ssh//Dropbear sshd 2025.89 (protocol 2.0)/, 80/filtered/tcp//http///, 443/filtered/tcp//https///, 8080/filtered/tcp//http-proxy///
22/open/tcp//ssh//OpenSSH 10.0p2 Debian 7+deb13u4 (protocol 2.0)/, 80/filtered/tcp//http///, 111/open/tcp//rpcbind///, 443/filtered/tcp//https///, 2049/open/tcp//rpcbind///, 5900/open/tcp//vnc//VNC (protocol 3.8)/, 8080/filtered/tcp//http-proxy///
22/open/tcp//ssh//OpenSSH 10.0p2 Debian 7+deb13u4 (protocol 2.0)/, 80/open/tcp//http//Golang net|http server (Go-IPFS json-rpc or InfluxDB API)/, 111/open/tcp//rpcbind///, 443/open/tcp//ssl|http//Golang net|http server (Go-IPFS json-rpc or InfluxDB API)/, 2049/open/tcp//rpcbind///, 5900/open/tcp//vnc//VNC (protocol 3.8)/, 8080/open/tcp//http//Werkzeug httpd 3.1.8 (Python 3.11.15)/
3000/open/tcp//tcpwrapped///
8080/open/tcp//http//lighttpd/
22/open/tcp//ssh//OpenSSH 10.3p1 Debian 1 (protocol 2.0)/, 3389/open/tcp//tcpwrapped///
```

## Cloud accounts

- **AWS:** 347694270918
- **Azure:** not authenticated
- **GCP:** gcloud not installed

## Files in this report

- `cloud`  (4096 bytes)
- `disks.json`  (5024 bytes)
- `disk_usage.txt`  (1399 bytes)
- `filesystem.txt`  (2874 bytes)
- `live_hosts.txt`  (122 bytes)
- `network_passive.txt`  (14330 bytes)
- `nmap_ping.gnmap`  (673 bytes)
- `nmap_ping.txt`  (1316 bytes)
- `nmap_safe_scripts.txt`  (17136 bytes)
- `nmap_services.gnmap`  (2644 bytes)
- `nmap_services.txt`  (9284 bytes)
- `nmap_services.xml`  (23037 bytes)
- `scan.log`  (2194 bytes)
- `secrets_audit.txt`  (4681 bytes)
- `services.txt`  (34758 bytes)
- `software.txt`  (9095 bytes)
- `summary.md`  (4353 bytes)
- `system.json`  (548 bytes)
