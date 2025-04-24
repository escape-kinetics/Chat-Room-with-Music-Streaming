import os
import socket
import threading
import time

LIBRARY_DIR = "library"
PLAYLIST_DIR = "playlist"

HOST = '127.0.0.1'
PORT = 12345

clients = {}  # Changed from set to dict to store client names
clients_lock = threading.Lock()

os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(PLAYLIST_DIR, exist_ok=True)

def list_files(directory):
    return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

def broadcast_message(sender_name, message):
    """Send a message to all connected clients"""
    broadcast_data = f"{sender_name}: {message}".encode()
    with clients_lock:
        for client_conn, client_name in clients.items():
            try:
                client_conn.sendall(b"CHAT_MESSAGE\n" + broadcast_data)
            except:
                pass

def handle_client(conn, addr):
    client_name = None
    
    try:
        # First message should be the client's name
        name_request = conn.recv(1024).decode().strip()
        if name_request.startswith('JOIN_CHAT'):
            _, client_name = name_request.split(maxsplit=1)
            with clients_lock:
                clients[conn] = client_name
            
            # First send the success response
            conn.sendall(b"JOIN_SUCCESS")
            
            # Then notify everyone about the new user
            broadcast_message("SERVER", f"{client_name} has joined the chat")
        else:
            conn.sendall(b"Error: First command must be JOIN_CHAT")
            return
        
        # Main client handling loop
        while True:
            request = conn.recv(1024).decode().strip()
            if not request:
                break
                
            print(f"[{addr}] [{client_name}] {request}")
            
            if request.startswith('CHAT'):
                _, message = request.split(maxsplit=1)
                broadcast_message(client_name, message)
                conn.sendall(b"MESSAGE_SENT")
                
            elif request == 'LIST_LIBRARY_SONGS':
                conn.sendall(b"COMMAND_RESPONSE\n" + '\n'.join(list_files(LIBRARY_DIR)).encode())

            elif request == 'LIST_PLAYLISTS':
                conn.sendall(b"COMMAND_RESPONSE\n" + '\n'.join(list_files(PLAYLIST_DIR)).encode())

            elif request.startswith('LIST_SONGS_IN_PLAYLIST'):
                _, name = request.split(maxsplit=1)
                try:
                    with open(os.path.join(PLAYLIST_DIR, name)) as f:
                        conn.sendall(b"COMMAND_RESPONSE\n" + f.read().strip().encode())
                except:
                    conn.sendall(b"COMMAND_RESPONSE\nError: Playlist not found")

            elif request.startswith('CREATE_PLAYLIST'):
                _, name = request.split(maxsplit=1)
                path = os.path.join(PLAYLIST_DIR, name)
                if os.path.exists(path):
                    conn.sendall(b"COMMAND_RESPONSE\nPlaylist already exists")
                else:
                    open(path, 'w').close()
                    conn.sendall(b"COMMAND_RESPONSE\nPlaylist created")
                    broadcast_message("SERVER", f"{client_name} created a new playlist: {name}")

            elif request.startswith('ADD_SONG_TO_PLAYLIST'):
                _, pl, song = request.split(maxsplit=2)
                pl_path = os.path.join(PLAYLIST_DIR, pl)
                song_path = os.path.join(LIBRARY_DIR, song)
                if os.path.exists(pl_path) and os.path.exists(song_path):
                    with open(pl_path, 'a') as f:
                        f.write(song + '\n')
                    conn.sendall(b"COMMAND_RESPONSE\nSong added")
                    broadcast_message("SERVER", f"{client_name} added {song} to playlist {pl}")
                else:
                    conn.sendall(b"COMMAND_RESPONSE\nError adding song")

            elif request.startswith('REMOVE_SONG_FROM_PLAYLIST'):
                _, pl, song = request.split(maxsplit=2)
                pl_path = os.path.join(PLAYLIST_DIR, pl)
                if os.path.exists(pl_path):
                    with open(pl_path, 'r') as f:
                        lines = f.readlines()
                    with open(pl_path, 'w') as f:
                        f.writelines(line for line in lines if line.strip() != song)
                    conn.sendall(b"COMMAND_RESPONSE\nSong removed")
                else:
                    conn.sendall(b"COMMAND_RESPONSE\nPlaylist not found")

            elif request.startswith('DELETE_PLAYLIST'):
                _, name = request.split(maxsplit=1)
                path = os.path.join(PLAYLIST_DIR, name)
                try:
                    os.remove(path)
                    conn.sendall(b"COMMAND_RESPONSE\nPlaylist deleted")
                    broadcast_message("SERVER", f"{client_name} deleted playlist {name}")
                except:
                    conn.sendall(b"COMMAND_RESPONSE\nError deleting playlist")

            elif request.startswith('MERGE_PLAYLISTS'):
                _, source, target = request.split(maxsplit=2)
                src_path = os.path.join(PLAYLIST_DIR, source)
                tgt_path = os.path.join(PLAYLIST_DIR, target)
                if os.path.exists(src_path) and os.path.exists(tgt_path):
                    with open(src_path) as src:
                        src_songs = src.read().strip().splitlines()
                    with open(tgt_path, 'a') as tgt:
                        for song in src_songs:
                            tgt.write(song + '\n')
                    conn.sendall(b"COMMAND_RESPONSE\nPlaylists merged")
                    broadcast_message("SERVER", f"{client_name} merged playlists {source} into {target}")
                else:
                    conn.sendall(b"COMMAND_RESPONSE\nOne or both playlists not found")

            elif request.startswith('COMBINE_PLAYLISTS'):
                _, p1, p2 = request.split(maxsplit=2)
                p1_path = os.path.join(PLAYLIST_DIR, p1)
                p2_path = os.path.join(PLAYLIST_DIR, p2)
                combined_name = f"{p1}_{p2}_combined"
                combined_path = os.path.join(PLAYLIST_DIR, combined_name)

                if os.path.exists(p1_path) and os.path.exists(p2_path):
                    with open(p1_path) as f1, open(p2_path) as f2:
                        combined_songs = set(f1.read().splitlines() + f2.read().splitlines())
                    with open(combined_path, 'w') as f:
                        for song in combined_songs:
                            f.write(song + '\n')
                    conn.sendall(f"COMMAND_RESPONSE\nCombined into playlist: {combined_name}".encode())
                    broadcast_message("SERVER", f"{client_name} created a combined playlist: {combined_name}")
                else:
                    conn.sendall(b"COMMAND_RESPONSE\nOne or both playlists not found")

            elif request.startswith('STREAM_SONG'):
                _, song = request.split(maxsplit=1)
                path = os.path.join(LIBRARY_DIR, song)
                if os.path.exists(path):
                    broadcast_message("SERVER", f"{client_name} is now streaming: {song}")
                    conn.sendall(b"STREAM_START\n")
                    
                    with open(path, 'rb') as f:
                        while True:
                            data = f.read(1024)
                            if not data:
                                break
                            try:
                                conn.sendall(data)
                            except:
                                break
                    
                    conn.sendall(b"STREAM_END\n")
                else:
                    conn.sendall(b"COMMAND_RESPONSE\nError: Song not found")

            elif request == 'LEAVE_CHAT':
                break
                
            else:
                conn.sendall(b"COMMAND_RESPONSE\nInvalid command")

    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        # Clean up when client disconnects
        with clients_lock:
            if conn in clients:
                leaving_name = clients[conn]
                del clients[conn]
                if client_name:
                    broadcast_message("SERVER", f"{client_name} has left the chat")
        
        try:
            conn.close()
        except:
            pass

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Chat and Music Streaming Server running on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            print(f"New connection from {addr}")
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    start_server()
