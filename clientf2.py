import os
import socket
import threading
import pygame
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12345

class MusicChatClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Streaming Chatroom")
        self.root.geometry("950x650")
        self.root.minsize(800, 500)

        # Networking and playback
        self.socket = None
        self.connected = False
        self.username = None
        self.receive_thread = None
        self.streaming_mode = False
        self.current_download = None
        self.download_file = None
        self.last_stream_request = ""
        self.last_command = ""
        self.current_song = None

        # Audio
        pygame.init()
        pygame.mixer.init()
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

        # UI
        self.status_var = tk.StringVar(value="Not connected")
        self.now_playing_var = tk.StringVar(value="No song playing")

        self.build_ui()
        self.set_ui_state(False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.login_frame = ttk.LabelFrame(self.main_frame, text="Login")
        self.login_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(self.login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(self.login_frame, textvariable=self.username_var)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.connect_button = ttk.Button(self.login_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(self.login_frame, textvariable=self.status_var).grid(row=0, column=3, padx=5, pady=5)

        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Chat section
        self.chat_frame = ttk.LabelFrame(self.paned_window, text="Chat")
        self.paned_window.add(self.chat_frame, weight=1)
        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, state=tk.DISABLED, height=16)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_input_frame = ttk.Frame(self.chat_frame)
        self.chat_input_frame.pack(fill=tk.X, padx=5, pady=5)
        self.chat_input = ttk.Entry(self.chat_input_frame)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self.send_chat_message)
        self.send_button = ttk.Button(self.chat_input_frame, text="Send", command=self.send_chat_message)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        # Music section
        self.music_frame = ttk.LabelFrame(self.paned_window, text="Music")
        self.paned_window.add(self.music_frame, weight=1)
        self.notebook = ttk.Notebook(self.music_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Library tab
        self.library_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.library_frame, text="Library")
        self.library_list = tk.Listbox(self.library_frame)
        self.library_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.library_list.bind("<Double-1>", self.play_selected_song)
        self.library_button_frame = ttk.Frame(self.library_frame)
        self.library_button_frame.pack(fill=tk.X, padx=5, pady=5)
        self.refresh_library_button = ttk.Button(self.library_button_frame, text="Refresh", command=self.refresh_library)
        self.refresh_library_button.pack(side=tk.LEFT, padx=5)
        self.play_library_button = ttk.Button(self.library_button_frame, text="Play", command=self.play_selected_song)
        self.play_library_button.pack(side=tk.LEFT, padx=5)

        # Playlists tab
        self.playlists_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.playlists_frame, text="Playlists")
        self.playlists_pane = ttk.PanedWindow(self.playlists_frame, orient=tk.HORIZONTAL)
        self.playlists_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.playlists_list_frame = ttk.Frame(self.playlists_pane)
        self.playlists_pane.add(self.playlists_list_frame, weight=1)
        ttk.Label(self.playlists_list_frame, text="Playlists:").pack(anchor=tk.W, padx=5, pady=2)
        self.playlists_list = tk.Listbox(self.playlists_list_frame, selectmode=tk.SINGLE)
        self.playlists_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.playlists_list.bind("<<ListboxSelect>>", self.load_playlist_songs)
        self.playlist_button_frame = ttk.Frame(self.playlists_list_frame)
        self.playlist_button_frame.pack(fill=tk.X, padx=5, pady=5)
        self.refresh_playlists_button = ttk.Button(self.playlist_button_frame, text="Refresh", command=self.refresh_playlists)
        self.refresh_playlists_button.pack(side=tk.LEFT, padx=2)
        self.create_playlist_button = ttk.Button(self.playlist_button_frame, text="Create", command=self.create_playlist)
        self.create_playlist_button.pack(side=tk.LEFT, padx=2)
        self.delete_playlist_button = ttk.Button(self.playlist_button_frame, text="Delete", command=self.delete_playlist)
        self.delete_playlist_button.pack(side=tk.LEFT, padx=2)
        self.merge_playlist_button = ttk.Button(self.playlist_button_frame, text="Merge", command=self.merge_playlists)
        self.merge_playlist_button.pack(side=tk.LEFT, padx=2)
        self.combine_playlist_button = ttk.Button(self.playlist_button_frame, text="Combine", command=self.combine_playlists)
        self.combine_playlist_button.pack(side=tk.LEFT, padx=2)
        self.view_playlist_button = ttk.Button(self.playlist_button_frame, text="View by Name", command=self.view_playlist_by_name)
        self.view_playlist_button.pack(side=tk.LEFT, padx=2)

        self.playlist_songs_frame = ttk.Frame(self.playlists_pane)
        self.playlists_pane.add(self.playlist_songs_frame, weight=1)
        self.playlist_name_var = tk.StringVar(value="No playlist selected")
        ttk.Label(self.playlist_songs_frame, textvariable=self.playlist_name_var).pack(anchor=tk.W, padx=5, pady=2)
        self.playlist_songs_list = tk.Listbox(self.playlist_songs_frame)
        self.playlist_songs_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.playlist_songs_list.bind("<Double-1>", self.play_selected_playlist_song)
        self.playlist_songs_button_frame = ttk.Frame(self.playlist_songs_frame)
        self.playlist_songs_button_frame.pack(fill=tk.X, padx=5, pady=5)
        self.play_playlist_song_button = ttk.Button(self.playlist_songs_button_frame, text="Play", command=self.play_selected_playlist_song)
        self.play_playlist_song_button.pack(side=tk.LEFT, padx=2)
        self.add_to_playlist_button = ttk.Button(self.playlist_songs_button_frame, text="Add Song", command=self.add_song_to_playlist)
        self.add_to_playlist_button.pack(side=tk.LEFT, padx=2)
        self.remove_from_playlist_button = ttk.Button(self.playlist_songs_button_frame, text="Remove", command=self.remove_song_from_playlist)
        self.remove_from_playlist_button.pack(side=tk.LEFT, padx=2)

        # Player tab
        self.player_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.player_frame, text="Player")
        ttk.Label(self.player_frame, text="Now Playing:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(self.player_frame, textvariable=self.now_playing_var, font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        self.player_controls_frame = ttk.Frame(self.player_frame)
        self.player_controls_frame.pack(fill=tk.X, padx=10, pady=10)
        self.play_pause_button = ttk.Button(self.player_controls_frame, text="Play/Pause", command=self.toggle_play_pause)
        self.play_pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(self.player_controls_frame, text="Stop", command=self.stop_playback)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.volume_frame = ttk.Frame(self.player_frame)
        self.volume_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(self.volume_frame, text="Volume:").pack(side=tk.LEFT, padx=5)
        self.volume_var = tk.DoubleVar(value=0.7)
        self.volume_slider = ttk.Scale(self.volume_frame, from_=0, to=1, orient=tk.HORIZONTAL,
                                       variable=self.volume_var, command=self.set_volume)
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        pygame.mixer.music.set_volume(0.7)

    def set_ui_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.chat_input.config(state=state)
        self.send_button.config(state=state)
        self.refresh_library_button.config(state=state)
        self.play_library_button.config(state=state)
        self.refresh_playlists_button.config(state=state)
        self.create_playlist_button.config(state=state)
        self.delete_playlist_button.config(state=state)
        self.merge_playlist_button.config(state=state)
        self.combine_playlist_button.config(state=state)
        self.view_playlist_button.config(state=state)
        self.play_playlist_song_button.config(state=state)
        self.add_to_playlist_button.config(state=state)
        self.remove_from_playlist_button.config(state=state)
        self.play_pause_button.config(state=state)
        self.stop_button.config(state=state)
        self.volume_slider.config(state=state)

    def connect_to_server(self):
        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.username = username
            self.socket.sendall(f"JOIN_CHAT {username}".encode())
            response = self.socket.recv(1024).decode().strip()
            if response == "JOIN_SUCCESS":
                self.connected = True
                self.status_var.set(f"Connected as {username}")
                self.connect_button.config(text="Disconnect", command=self.disconnect_from_server)
                self.set_ui_state(True)
                self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                self.receive_thread.start()
                self.refresh_library()
                self.refresh_playlists()
                self.add_chat_message("SERVER", f"Welcome, {username}!")
            else:
                messagebox.showerror("Connection Error", f"Failed to join: {response}")
                self.socket.close()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Error connecting to server: {e}")
            try:
                self.socket.close()
            except:
                pass

    def disconnect_from_server(self):
        if self.connected:
            try:
                self.socket.sendall("LEAVE_CHAT".encode())
            except:
                pass
            self.connected = False
            try:
                self.socket.close()
            except:
                pass
            self.status_var.set("Not connected")
            self.connect_button.config(text="Connect", command=self.connect_to_server)
            self.set_ui_state(False)
            self.add_chat_message("CLIENT", "Disconnected from server")

    def add_chat_message(self, sender, message):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{sender}: {message}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def send_chat_message(self, event=None):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        message = self.chat_input.get().strip()
        if message:
            try:
                self.socket.sendall(f"CHAT {message}".encode())
                self.chat_input.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Error sending message: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)

    def receive_messages(self):
        while self.connected:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                if self.streaming_mode:
                    if b"STREAM_END\n" in data:
                        streaming_parts = data.split(b"STREAM_END\n", 1)
                        if streaming_parts[0]:
                            self.download_file.write(streaming_parts[0])
                        self.download_file.close()
                        try:
                            full_path = os.path.join(self.download_dir, self.current_download)
                            pygame.mixer.music.load(full_path)
                            pygame.mixer.music.play()
                            self.current_song = self.current_download
                            self.now_playing_var.set(self.current_song)
                            self.add_chat_message("CLIENT", f"Now playing: {self.current_song}")
                        except Exception as e:
                            self.add_chat_message("ERROR", f"Error playing music: {e}")
                        self.streaming_mode = False
                        if len(streaming_parts) > 1 and streaming_parts[1]:
                            self.process_message(streaming_parts[1])
                    else:
                        self.download_file.write(data)
                else:
                    self.process_message(data)
            except Exception as e:
                if self.connected:
                    self.root.after(0, lambda: messagebox.showerror("Connection Error", f"Error receiving data: {e}"))
                    self.connected = False
                    self.root.after(0, lambda: self.status_var.set("Connection lost"))
                    self.root.after(0, lambda: self.set_ui_state(False))
                break

    def process_message(self, data):
        try:
            if data.startswith(b"CHAT_MESSAGE\n"):
                message = data[len(b"CHAT_MESSAGE\n"):].decode()
                sender, content = message.split(":", 1)
                self.root.after(0, lambda: self.add_chat_message(sender.strip(), content.strip()))
            elif data.startswith(b"COMMAND_RESPONSE\n"):
                response = data[len(b"COMMAND_RESPONSE\n"):].decode()
                self.root.after(0, lambda: self.add_chat_message("SERVER", response))
                if "LIST_LIBRARY_SONGS" in self.last_command:
                    songs = response.strip().split('\n')
                    self.root.after(0, lambda: self.update_library_list(songs))
                elif "LIST_PLAYLISTS" in self.last_command:
                    playlists = response.strip().split('\n')
                    self.root.after(0, lambda: self.update_playlists_list(playlists))
                elif "LIST_SONGS_IN_PLAYLIST" in self.last_command:
                    songs = response.strip().split('\n')
                    self.root.after(0, lambda: self.update_playlist_songs_list(songs))
            elif data.startswith(b"STREAM_START\n"):
                song_name = self.last_stream_request.split()[-1]
                self.root.after(0, lambda: self.add_chat_message("CLIENT", f"Receiving song: {song_name}"))
                self.current_download = song_name
                download_path = os.path.join(self.download_dir, self.current_download)
                self.download_file = open(download_path, "wb")
                self.streaming_mode = True
                stream_parts = data.split(b"STREAM_START\n", 1)
                if len(stream_parts) > 1 and stream_parts[1]:
                    if b"STREAM_END\n" in stream_parts[1]:
                        end_parts = stream_parts[1].split(b"STREAM_END\n", 1)
                        self.download_file.write(end_parts[0])
                        self.download_file.close()
                        try:
                            full_path = os.path.join(self.download_dir, self.current_download)
                            pygame.mixer.music.load(full_path)
                            pygame.mixer.music.play()
                            self.current_song = self.current_download
                            self.root.after(0, lambda: self.now_playing_var.set(self.current_song))
                            self.root.after(0, lambda: self.add_chat_message("CLIENT", f"Now playing: {self.current_song}"))
                        except Exception as e:
                            self.root.after(0, lambda: self.add_chat_message("ERROR", f"Error playing music: {e}"))
                        self.streaming_mode = False
                        if len(end_parts) > 1 and end_parts[1]:
                            self.process_message(end_parts[1])
                    else:
                        self.download_file.write(stream_parts[1])
        except Exception as e:
            self.root.after(0, lambda: self.add_chat_message("ERROR", f"Error processing message: {e}"))

    def update_library_list(self, songs):
        self.library_list.delete(0, tk.END)
        for song in songs:
            if song and not song.startswith("Error:"):
                self.library_list.insert(tk.END, song)

    def update_playlists_list(self, playlists):
        self.playlists_list.delete(0, tk.END)
        for playlist in playlists:
            if playlist and not playlist.startswith("Error:"):
                self.playlists_list.insert(tk.END, playlist)

    def update_playlist_songs_list(self, songs):
        self.playlist_songs_list.delete(0, tk.END)
        for song in songs:
            if song and not song.startswith("Error:"):
                self.playlist_songs_list.insert(tk.END, song)

    def refresh_library(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        try:
            self.last_command = "LIST_LIBRARY_SONGS"
            self.socket.sendall(self.last_command.encode())
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.connected = False
            self.status_var.set("Connection lost")
            self.set_ui_state(False)

    def refresh_playlists(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        try:
            self.last_command = "LIST_PLAYLISTS"
            self.socket.sendall(self.last_command.encode())
            self.playlist_songs_list.delete(0, tk.END)
            self.playlist_name_var.set("No playlist selected")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.connected = False
            self.status_var.set("Connection lost")
            self.set_ui_state(False)

    def load_playlist_songs(self, event=None):
        if not self.connected:
            return
        selection = self.playlists_list.curselection()
        if not selection:
            return
        playlist_name = self.playlists_list.get(selection[0])
        self.playlist_name_var.set(f"Playlist: {playlist_name}")
        try:
            self.last_command = f"LIST_SONGS_IN_PLAYLIST {playlist_name}"
            self.socket.sendall(self.last_command.encode())
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.connected = False
            self.status_var.set("Connection lost")
            self.set_ui_state(False)

    def create_playlist(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        playlist_name = simpledialog.askstring("Create Playlist", "Enter playlist name:")
        if playlist_name:
            try:
                self.last_command = f"CREATE_PLAYLIST {playlist_name}"
                self.socket.sendall(self.last_command.encode())
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)

    def delete_playlist(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        selection = self.playlists_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a playlist to delete")
            return
        playlist_name = self.playlists_list.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete playlist '{playlist_name}'?"):
            try:
                self.last_command = f"DELETE_PLAYLIST {playlist_name}"
                self.socket.sendall(self.last_command.encode())
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)

    def add_song_to_playlist(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        playlist_selection = self.playlists_list.curselection()
        if not playlist_selection:
            messagebox.showinfo("No Selection", "Please select a playlist")
            return
        playlist_name = self.playlists_list.get(playlist_selection[0])
        song_dialog = tk.Toplevel(self.root)
        song_dialog.title("Select Song")
        song_dialog.geometry("300x400")
        song_dialog.transient(self.root)
        song_dialog.grab_set()
        ttk.Label(song_dialog, text="Select a song to add:").pack(padx=10, pady=5, anchor=tk.W)
        song_listbox = tk.Listbox(song_dialog)
        song_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for i in range(self.library_list.size()):
            song_listbox.insert(tk.END, self.library_list.get(i))
        def add_selected_song():
            song_selection = song_listbox.curselection()
            if not song_selection:
                messagebox.showinfo("No Selection", "Please select a song")
                return
            song_name = song_listbox.get(song_selection[0])
            try:
                self.last_command = f"ADD_SONG_TO_PLAYLIST {playlist_name} {song_name}"
                self.socket.sendall(self.last_command.encode())
                song_dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)
        ttk.Button(song_dialog, text="Add", command=add_selected_song).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(song_dialog, text="Cancel", command=song_dialog.destroy).pack(side=tk.RIGHT, padx=10, pady=10)

    def remove_song_from_playlist(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        playlist_selection = self.playlists_list.curselection()
        song_selection = self.playlist_songs_list.curselection()
        if not playlist_selection or not song_selection:
            messagebox.showinfo("No Selection", "Please select a playlist and a song to remove")
            return
        playlist_name = self.playlists_list.get(playlist_selection[0])
        song_name = self.playlist_songs_list.get(song_selection[0])
        try:
            self.last_command = f"REMOVE_SONG_FROM_PLAYLIST {playlist_name} {song_name}"
            self.socket.sendall(self.last_command.encode())
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.connected = False
            self.status_var.set("Connection lost")
            self.set_ui_state(False)

    def play_selected_song(self, event=None):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        selection = self.library_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a song to play")
            return
        song_name = self.library_list.get(selection[0])
        self.stream_song(song_name)

    def play_selected_playlist_song(self, event=None):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        selection = self.playlist_songs_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a song to play")
            return
        song_name = self.playlist_songs_list.get(selection[0])
        self.stream_song(song_name)

    def stream_song(self, song_name):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        try:
            self.last_stream_request = f"STREAM_SONG {song_name}"
            self.socket.sendall(self.last_stream_request.encode())
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def toggle_play_pause(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.add_chat_message("CLIENT", "Playback paused")
        else:
            pygame.mixer.music.unpause()
            self.add_chat_message("CLIENT", "Playback resumed")

    def stop_playback(self):
        pygame.mixer.music.stop()
        self.now_playing_var.set("No song playing")
        self.add_chat_message("CLIENT", "Playback stopped")

    def set_volume(self, value):
        volume = float(value)
        pygame.mixer.music.set_volume(volume)

    def merge_playlists(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        selected = self.playlists_list.curselection()
        if len(selected) != 1:
            messagebox.showinfo("Selection", "Select exactly one source playlist to merge")
            return
        source_playlist = self.playlists_list.get(selected[0])
        # Create window to select target playlist via radio buttons
        merge_win = tk.Toplevel(self.root)
        merge_win.title("Select Target Playlist for Merge")
        merge_win.geometry("300x400")
        merge_win.transient(self.root)
        merge_win.grab_set()
        ttk.Label(merge_win, text=f"Source playlist: {source_playlist}", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Label(merge_win, text="Select target playlist to merge into:").pack(pady=5)
        target_var = tk.StringVar()
        playlists = [self.playlists_list.get(i) for i in range(self.playlists_list.size()) if self.playlists_list.get(i) != source_playlist]
        if not playlists:
            messagebox.showinfo("No Target", "No other playlists available to merge into")
            merge_win.destroy()
            return
        for pl in playlists:
            ttk.Radiobutton(merge_win, text=pl, variable=target_var, value=pl).pack(anchor=tk.W, padx=10, pady=2)
        def confirm_merge():
            target = target_var.get()
            if not target:
                messagebox.showinfo("Selection", "Please select a target playlist")
                return
            try:
                self.last_command = f"MERGE_PLAYLISTS {source_playlist} {target}"
                self.socket.sendall(self.last_command.encode())
                merge_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)
        ttk.Button(merge_win, text="Merge", command=confirm_merge).pack(pady=10)
        ttk.Button(merge_win, text="Cancel", command=merge_win.destroy).pack()

    def combine_playlists(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        selected = self.playlists_list.curselection()
        if len(selected) != 1:
            messagebox.showinfo("Selection", "Select exactly one playlist as first to combine")
            return
        playlist1 = self.playlists_list.get(selected[0])
        combine_win = tk.Toplevel(self.root)
        combine_win.title("Combine Playlists")
        combine_win.geometry("350x350")
        combine_win.transient(self.root)
        combine_win.grab_set()
        ttk.Label(combine_win, text=f"First playlist: {playlist1}", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Label(combine_win, text="Select second playlist to combine with:").pack(pady=5)
        second_var = tk.StringVar()
        playlists = [self.playlists_list.get(i) for i in range(self.playlists_list.size()) if self.playlists_list.get(i) != playlist1]
        if not playlists:
            messagebox.showinfo("No Target", "No other playlists available to combine with")
            combine_win.destroy()
            return
        for pl in playlists:
            ttk.Radiobutton(combine_win, text=pl, variable=second_var, value=pl).pack(anchor=tk.W, padx=10, pady=2)
        ttk.Label(combine_win, text="Enter name for the new combined playlist:").pack(pady=5)
        new_name_var = tk.StringVar()
        new_name_entry = ttk.Entry(combine_win, textvariable=new_name_var)
        new_name_entry.pack(padx=10, pady=5, fill=tk.X)
        def confirm_combine():
            playlist2 = second_var.get()
            new_name = new_name_var.get().strip()
            if not playlist2:
                messagebox.showinfo("Selection", "Please select the second playlist")
                return
            if not new_name:
                messagebox.showinfo("Input Needed", "Please enter a name for the combined playlist")
                return
            try:
                self.last_command = f"COMBINE_PLAYLISTS {playlist1} {playlist2} {new_name}"
                self.socket.sendall(self.last_command.encode())
                combine_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.connected = False
                self.status_var.set("Connection lost")
                self.set_ui_state(False)
        ttk.Button(combine_win, text="Combine", command=confirm_combine).pack(pady=10)
        ttk.Button(combine_win, text="Cancel", command=combine_win.destroy).pack()

    def view_playlist_by_name(self):
        if not self.connected:
            messagebox.showinfo("Not Connected", "You must connect to the server first")
            return
        playlist_name = simpledialog.askstring("View Playlist", "Enter playlist name:")
        if not playlist_name:
            return
        try:
            self.last_command = f"LIST_SONGS_IN_PLAYLIST {playlist_name}"
            self.socket.sendall(self.last_command.encode())
            self.playlist_name_var.set(f"Playlist: {playlist_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.connected = False
            self.status_var.set("Connection lost")
            self.set_ui_state(False)

    def on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            if self.connected:
                self.disconnect_from_server()
            pygame.quit()
            self.root.destroy()

def main():
    root = tk.Tk()
    app = MusicChatClientGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
