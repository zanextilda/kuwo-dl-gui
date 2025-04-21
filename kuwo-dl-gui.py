import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import requests
from io import BytesIO
import json
import threading
import subprocess
import os
import re
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC
from mutagen.flac import Picture

try:
    os.makedirs('Downloads')
except FileExistsError:
    pass


def sanitize_filename(filename):
    disallowed_characters = re.compile(r"[=_()/-?]")
    sanitized = disallowed_characters.sub('', filename)
    max_length = 255
    sanitized = sanitized[:max_length]
    sanitized = sanitized.strip()
    
    return sanitized

class AlbumApp:
    def __init__(self, root, data):
        self.root = root
        self.root.title("kuwo-dl-gui")
        self.root.geometry("1280x720")

        self.data = data
        self.image_url = self.data.get("image_url", "")
        self.songs = self.data.get("songs", [])
        self.active_downloads = 0
        self.download_entries = []
        self.completed_downloads = []
        
        self.download_semaphore = threading.Semaphore(4) #set number of parallel downloads, increasing this number could cause the program to freeze :)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.info_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.info_tab, text="Info")

        self.download_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.download_tab, text="Downloads")

        self.search_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.search_tab, text="Search")

        self.setup_info_tab()

        self.clear_completed_button = ttk.Button(self.download_tab, text="Clear Completed", command=self.clear_completed_downloads)
        self.clear_completed_button.pack(pady=(10, 5), padx=10)

        self.download_list_frame = ttk.Frame(self.download_tab)
        self.download_list_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.setup_search_tab()
        self.update_tab_title()

    def setup_info_tab(self):
        self.clear_info_tab()

        info_frame = ttk.Frame(self.info_tab, padding=10)
        info_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.image_frame = ttk.Frame(info_frame)
        self.image_frame.grid(row=0, column=0, padx=10, sticky="nw")

        if self.image_url:
            self.load_image(self.image_url)
            
        download_cover_button = ttk.Button(self.image_frame, text="Download Cover", command=self.download_cover)
        download_cover_button.pack(pady=(10, 0))

        self.url_frame = ttk.Frame(info_frame)
        self.url_frame.grid(row=0, column=2, padx=(10, 0), sticky="ne")

        self.url_entry = ttk.Entry(self.url_frame, width=30)
        self.url_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.parse_button = ttk.Button(self.url_frame, text="Parse URL", command=self.parse_url)
        self.parse_button.pack(side=tk.LEFT)

        self.select_all_button = ttk.Button(self.image_frame, text="Select All", command=self.select_all)
        self.select_all_button.pack(pady=(10, 0))

        self.deselect_all_button = ttk.Button(self.image_frame, text="Deselect All", command=self.deselect_all)
        self.deselect_all_button.pack(pady=(10, 0))

        self.download_selected_button = ttk.Button(self.image_frame, text="Download Selected", command=self.download_selected)
        self.download_selected_button.pack(pady=(10, 0))

        self.song_frame = ttk.Frame(info_frame)
        self.song_frame.grid(row=0, column=1, sticky="nsew")
        info_frame.grid_rowconfigure(0, weight=1)

        max_title_length = max(len(f"{song['artist']} - {song['title']}") for song in self.songs) if self.songs else 0
        text_width = max(max_title_length, 30)

        self.check_vars = {}
        for song in self.songs:
            self.display_song(song, text_width)

    def clear_info_tab(self):
        for widget in self.info_tab.winfo_children():
            widget.destroy()

    def setup_search_tab(self):
        search_frame = ttk.Frame(self.search_tab, padding=10)
        search_frame.pack(fill="both", expand=True)

        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(pady=10)

        self.search_button = ttk.Button(search_frame, text='Search', command=self.start_search)
        self.search_button.pack(pady=5)

        self.results_frame = ttk.Frame(search_frame)
        self.results_frame.pack(pady=10, fill=tk.BOTH, expand=True)

    def load_image(self, url):
        response = requests.get(url)
        img_data = response.content
        img = Image.open(BytesIO(img_data))
        img = img.resize((250, 250), Image.LANCZOS)
        self.image = ImageTk.PhotoImage(img)

        img_label = ttk.Label(self.image_frame, image=self.image)
        img_label.pack()

    def download_cover(self):
        modified_url = self.image_url.replace('/250/', '/0/')
        print(f"Downloading cover from {modified_url}")

        try:
            response = requests.get(modified_url)
            response.raise_for_status()

            cover_filename = "cover_art.jpg"
            with open(cover_filename, "wb") as f:
                f.write(response.content)

            print(f"Cover art downloaded successfully as {cover_filename}!")

        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred while downloading cover art: {err}")
        except Exception as ex:
            print(f"An error occurred while downloading cover art: {ex}")

    def update_tab_title(self):
        if self.active_downloads == 0:
            self.notebook.tab(self.download_tab, text="Downloads")
        else:
            self.notebook.tab(self.download_tab, text=f"Downloads [{self.active_downloads}]")

    def download_song(self, song_id, song_title):
        threading.Thread(target=self.start_download, args=(song_id, song_title)).start()

    def start_download(self, song_id, song_title):
        with self.download_semaphore:
            self.active_downloads += 1
            self.update_tab_title()

            try:
                url_response = requests.get(f"https://mobi.kuwo.cn/mobi.s?f=web&type=&type=convert_url_with_sign&rid={song_id}&format=mp3&br=2000kflac&source=kwplayer_ar_4.4.2.7_B_nuoweida_vh.apk&mobi=1").json()
                url = url_response['data']['url'].split('?')[0]
                ext = url.split('.')[-1]

                if song_title.endswith(' '):
                    song_title = song_title[:-1]

                print(f"Attempting to download: {song_title} from {url}")

                self.download_file(url, song_title)

            except Exception as e:
                print(f"An error occurred while starting download for {song_title}: {e}")
            finally:
                self.active_downloads -= 1
                self.update_tab_title()

    def download_file(self, url, song_title):
        try:
            head_response = requests.head(url)
            total_length = int(head_response.headers.get('content-length', 0))
            ext = url.split('.')[-1]

            if song_title.endswith(' '):
                song_title = song_title[:-1]

            filename = f"Downloads/{sanitize_filename(song_title)}.{ext}"
            with open(filename, "wb") as f:
                downloaded = 0

                progress_frame = ttk.Frame(self.download_list_frame)
                progress_frame.pack(pady=5, anchor='w')

                percent_label = ttk.Label(progress_frame, text="0%")
                percent_label.pack(side=tk.LEFT)

                progress_bar = ttk.Progressbar(progress_frame, mode="determinate", length=300)
                progress_bar.pack(side=tk.LEFT, padx=10)

                song_label = ttk.Label(progress_frame, text=f"{song_title}.{ext}")
                song_label.pack(side=tk.LEFT)

                self.download_entries.append((progress_frame, percent_label, progress_bar, song_label))

                with requests.get(url, stream=True) as response:
                    response.raise_for_status()

                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_length > 0:
                            progress = (downloaded / total_length) * 100
                            progress_bar['value'] = progress
                            percent_label['text'] = f"{int(progress)}%"
                            self.root.update_idletasks()

                self.add_cover_art(filename, song_title)

                progress_bar['value'] = 100
                percent_label['text'] = "100%"
                self.root.update_idletasks()

                self.completed_downloads.append((progress_frame, percent_label, progress_bar, song_label))

            print(f"{song_title} downloaded successfully as {filename}!")

        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred while downloading {song_title}: {err}")
        except Exception as ex:
            print(f"An error occurred while downloading {song_title}: {ex}")

    def add_cover_art(self, filename, song_title):
        cover_url = self.image_url.replace('/250/', '/0/')
        try:
            response = requests.get(cover_url)
            response.raise_for_status()
            
            cover_filename = "cover_art.jpg"
            with open(cover_filename, "wb") as cover_file:
                cover_file.write(response.content)

            if filename.endswith('.mp3'):
                audio = MP3(filename, ID3=ID3)
                with open(cover_filename, 'rb') as img_file:
                    audio.tags.add(APIC(mime='image/jpeg', type=3, desc='Cover', data=img_file.read()))
                audio.save()
            elif filename.endswith('.flac'):
                audio = FLAC(filename)
                with open(cover_filename, 'rb') as img_file:
                    img_data = img_file.read()
                    picture = Picture()
                    picture.data = img_data
                    picture.type = 3
                    picture.mime = 'image/jpeg'
                    picture.desc = 'Cover'
                    audio.add_picture(picture)
                audio.save()

            print(f"Cover art added to {filename}.")

        except Exception as e:
            print(f"Error adding cover art to {filename}: {e}")

    def clear_completed_downloads(self):
        for entry in self.completed_downloads:
            progress_frame, percent_label, progress_bar, song_label = entry
            progress_frame.pack_forget()
        self.completed_downloads.clear()

    def download_selected(self):
        for song in self.songs:
            if self.check_vars[song['id']].get():
                self.download_song(song['id'], song['title'])

    def select_all(self):
        for song in self.songs:
            self.check_vars[song['id']].set(True)

    def deselect_all(self):
        for song in self.songs:
            self.check_vars[song['id']].set(False)

    def display_song(self, song, text_width):
        song_frame = ttk.Frame(self.song_frame, padding="5")
        song_frame.pack(fill="x", padx=5, pady=5)

        var = tk.BooleanVar()
        self.check_vars[song['id']] = var
        song_checkbox = ttk.Checkbutton(song_frame, variable=var)
        song_checkbox.grid(row=0, column=0, padx=(0, 10), sticky='w')

        song_info = f"{song['artist'].replace('&', ', ')} - {song['title']}"
        song_label = ttk.Label(song_frame, text=song_info, width=text_width, anchor='w')
        song_label.grid(row=0, column=1, padx=(0, 10), sticky='w')

        filesize_label = ttk.Label(song_frame, text=song['filesize'], width=10)
        filesize_label.grid(row=0, column=3, sticky='w')

        download_icon = Image.open("download_icon.png")
        download_icon = download_icon.resize((15, 15), Image.LANCZOS)
        download_icon_image = ImageTk.PhotoImage(download_icon)

        download_button = ttk.Button(
            song_frame,
            image=download_icon_image,
            command=lambda: self.download_song(song['id'], song['title'])
        )
        download_button.image = download_icon_image
        download_button.grid(row=0, column=4, padx=(10, 0))

    def start_search(self):
        threading.Thread(target=self.perform_search).start()

    def perform_search(self):
        search_term = self.search_entry.get()
        search_url = f'https://search.kuwo.cn/r.s?client=kt&all={search_term}&pn=0&rn=10&vipver=1&ft=music&encoding=utf8&rformat=json&mobi=1'

        try:
            response = requests.get(search_url)
            data = response.json()

            for widget in self.results_frame.winfo_children():
                widget.destroy()

            for item in data['abslist']:
                self.display_search_result(item)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))

    def display_search_result(self, item):
        album = item['ALBUM']
        artist = item['ARTIST'].replace('&', ', ')
        song = item['SONGNAME']
        cover_url = "http://img2.sycdn.kuwo.cn/star/albumcover/" + item['web_albumpic_short']
        album_url = "https://www.kuwo.cn/album_detail/" + item['ALBUMID']
        song_url = "https://www.kuwo.cn/play_detail/" + item['DC_TARGETID']

        response = requests.get(cover_url)
        img_data = Image.open(BytesIO(response.content)).resize((50, 50), Image.LANCZOS)
        img = ImageTk.PhotoImage(img_data)

        frame = ttk.Frame(self.results_frame)
        frame.pack(pady=5, anchor='w')

        cover_label = ttk.Label(frame, image=img)
        cover_label.image = img
        cover_label.pack(side=tk.LEFT)

        info_label = ttk.Label(frame, text=f"{song}\n{artist}", justify=tk.LEFT)
        info_label.pack(side=tk.LEFT, padx=(5, 0))

        track_link = ttk.Label(frame, text="Copy track URL", foreground="blue", cursor="hand2")
        track_link.bind("<Button-1>", lambda e: self.on_link_click(track_link, song_url))
        track_link.pack(side=tk.LEFT)

        album_link = ttk.Label(frame, text="Copy album URL", foreground="blue", cursor="hand2")
        album_link.bind("<Button-1>", lambda e: self.on_link_click(album_link, album_url))
        album_link.pack(side=tk.LEFT, padx=(5, 0))

    def on_link_click(self, label, url):
        self.copy_to_clipboard(url)
        original_text = label['text']
        label['text'] = "Copied!"
        self.root.after(3000, lambda: label.config(text=original_text))

    def copy_to_clipboard(self, url):
        self.root.clipboard_clear()
        self.root.clipboard_append(url)

    def parse_url(self):
        url = self.url_entry.get()
        if url:
            try:
                subprocess.run(['python', 'parse_url.py', url], check=True)
                print(f"Running parse_url.py with URL: {url}")

                self.data = load_data_from_json("album_data.json")
                self.image_url = self.data.get("image_url", "")
                self.songs = self.data.get("songs", [])

                self.setup_info_tab()

            except subprocess.CalledProcessError as e:
                print(f"An error occurred while running the script: {e}")
                messagebox.showerror("Error", f"Failed to parse URL: {e}")
        else:
            messagebox.showwarning("Input Required", "Please enter a URL.")

def load_data_from_json(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

if __name__ == "__main__":
    root = tk.Tk()
    album_data = load_data_from_json("album_data.json")
    app = AlbumApp(root, album_data)
    root.mainloop()
