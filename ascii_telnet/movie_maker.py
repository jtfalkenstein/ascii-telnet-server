import subprocess
import tempfile
import uuid
from pathlib import Path

from ascii_telnet.ascii_movie import Movie
from hashlib import md5

current_directory = Path(__file__).parent
node_modules_dir = current_directory.parent / 'node_modules'
package_json = current_directory.parent / 'package.json'
ascii_video_package_dir = node_modules_dir / 'ascii-video'
temp_dir = Path(tempfile.gettempdir())

REQUIRED_NODE_VERSION = 7


def make_movie(
    video_path: str,
    processed_movie_path: str,
    node_executable_path: str = None,
    subtitles_path: str = None,
    seconds_per_slide: int = 3
):
    if not node_executable_path:
        node_executable_path = subprocess.run('which node', shell=True, capture_output=True, check=True)
    else:
        assert Path(node_executable_path).exists()
    if not _node_exists_with_right_version(node_executable_path):
        raise SystemError(f"You need node installed with at least version {REQUIRED_NODE_VERSION}")

    if not _ascii_video_is_installed():
        raise SystemError("npm install the package.json to ensure ascii-video is installed correctly.")

    video_hash = _hash_file(video_path)

    generated_yaml_file = _encode_video_to_ascii(video_path, video_hash, node_executable_path)
    movie = Movie()
    print("Loading frames into a movie file...")
    movie.load(str(generated_yaml_file))

    if subtitles_path:
        print("Splicing in subtitles...")
        movie.splice_in_text(subtitles_path, seconds_per_slide)

    print("Pickling move...")
    pickle_path = movie.to_pickle(processed_movie_path)
    print("Pickling complete!")
    return pickle_path


def _hash_file(video_filepath) -> str:
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

    md5_hash = md5()

    with open(video_filepath, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5_hash.update(data)

    return md5_hash.hexdigest()

def _node_exists_with_right_version(node_executable_path: str):
    node_version = subprocess.run(f'{node_executable_path} --version', shell=True, capture_output=True, encoding='utf-8')
    node_version_str = node_version.stdout
    assert node_version_str.startswith('v'), 'Unexpected node version output'
    major, minor, micro = node_version_str[1:].split('.')
    return int(major) >= REQUIRED_NODE_VERSION


def _ascii_video_is_installed():
    return ascii_video_package_dir.exists()


def _encode_video_to_ascii(video_path: str, video_hash: str, node_executable_path: str) -> Path:
    ascii_video_script_path = ascii_video_package_dir / 'main.js'
    output_file = temp_dir / f'{video_hash}.yaml'
    if output_file.exists():
        print("Video has already been transcoded to yaml. Using that file instead.")
    else:
        command = [
            node_executable_path,
            '--harmony',
            str(ascii_video_script_path),
            'create',
            video_path,
            str(output_file)
        ]

        subprocess.run(command, check=True)
    return output_file
