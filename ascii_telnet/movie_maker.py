import json
import subprocess
from pathlib import Path
import tempfile
import uuid
from ascii_telnet.ascii_movie import Movie

current_directory = Path(__file__).parent
node_modules_dir = current_directory.parent / 'node_modules'
package_json = current_directory.parent / 'package.json'
ascii_video_package_dir = node_modules_dir / 'ascii-video'
temp_dir = Path(tempfile.gettempdir())

REQUIRED_NODE_VERSION = 7


def make_movie(video_path: str, processed_movie_path: str, node_executable_path=None):
    if not node_executable_path:
        node_executable_path = subprocess.run('which node', shell=True, capture_output=True, check=True)
    else:
        assert Path(node_executable_path).exists()
    if not _node_exists_with_right_version(node_executable_path):
        raise SystemError(f"You need node installed with at least version {REQUIRED_NODE_VERSION}")

    if not _ascii_video_is_installed():
        raise SystemError("npm install the package.json to ensure ascii-video is installed correctly.")

    generated_yaml_file = _encode_video_to_ascii(video_path, node_executable_path)
    movie = Movie()
    print("Loading frames into a movie file...")
    movie.load(str(generated_yaml_file))
    print("Pickling move...")
    pickle_path = movie.to_pickle(processed_movie_path)
    print("Pickling complete!")
    return pickle_path



def _node_exists_with_right_version(node_executable_path: str):
    node_version = subprocess.run(f'{node_executable_path} --version', shell=True, capture_output=True, encoding='utf-8')
    node_version_str = node_version.stdout
    assert node_version_str.startswith('v'), 'Unexpected node version output'
    major, minor, micro = node_version_str[1:].split('.')
    return int(major) >= REQUIRED_NODE_VERSION


def _ascii_video_is_installed():
    return ascii_video_package_dir.exists()


def _encode_video_to_ascii(video_path: str, node_executable_path: str) -> Path:
    ascii_video_script_path = ascii_video_package_dir / 'main.js'
    output_file = temp_dir / (str(uuid.uuid4()) + '.yaml')

    command = [
        node_executable_path,
        '--harmony',
        str(ascii_video_script_path),
        'create',
        video_path,
        str(output_file)
    ]

    result = subprocess.run(command, check=True)
    return output_file