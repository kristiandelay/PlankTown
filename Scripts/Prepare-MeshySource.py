"""Normalize one Meshy archive, preserving original bytes and provenance.

Usage: python Scripts/Prepare-MeshySource.py ARCHIVE NAME DESTINATION
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(archive, name, destination):
    archive = Path(archive).resolve()
    destination = Path(destination).resolve()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', name):
        raise ValueError('Use an asset-safe PascalCase model name.')
    archive_bytes = archive.read_bytes()
    archive_hash = digest(archive_bytes)
    renamed_archive = archive.with_name(name + '.zip')
    if renamed_archive.exists() and renamed_archive != archive:
        if renamed_archive.read_bytes() != archive_bytes:
            raise FileExistsError(renamed_archive)
    planned = []
    mapped_names = set()
    channels = {'metallic': 'Metallic', 'normal': 'Normal', 'roughness': 'Roughness',
                'emissive': 'Emissive', 'ao': 'AO', 'opacity': 'Opacity',
                'basecolor': 'BaseColor', 'albedo': 'BaseColor'}
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            if member.is_dir():
                continue
            source = PurePosixPath(member.filename.replace('\\', '/'))
            if source.is_absolute() or '..' in source.parts or ':' in member.filename:
                raise ValueError('Unsafe archive member: ' + member.filename)
            if source.suffix.lower() == '.fbx':
                filename = name + '.fbx'
            elif source.suffix.lower() == '.png':
                stem = source.stem.lower()
                channel = 'BaseColor' if stem.endswith('_texture') else channels.get(stem.rsplit('_', 1)[-1])
                if not channel:
                    raise ValueError('Identify the texture channel before importing: ' + member.filename)
                filename = name + '_' + channel + '.png'
            else:
                raise ValueError('Unsupported archive member: ' + member.filename)
            if filename.casefold() in mapped_names:
                raise ValueError('Multiple files map to ' + filename + '; preserve separate material sets.')
            mapped_names.add(filename.casefold())
            data = package.read(member)
            output = destination / filename
            if output.exists() and output.read_bytes() != data:
                raise FileExistsError('Refusing to replace edited source: ' + str(output))
            planned.append((output, data, {'original': member.filename, 'file': filename,
                                         'bytes': len(data), 'sha256': digest(data)}))
    if sum(p[0].suffix == '.fbx' for p in planned) != 1:
        raise ValueError('Expected one FBX model; review this delivery separately.')
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / 'SourceManifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    if previous and previous.get('archive_sha256') != archive_hash:
        raise ValueError('The destination belongs to a different source archive.')
    original_name = previous.get('original_archive_name', archive.name)
    for output, data, _ in planned:
        if not output.exists():
            output.write_bytes(data)
    if renamed_archive != archive and not renamed_archive.exists():
        archive.rename(renamed_archive)
    project = Path(__file__).resolve().parents[1]
    manifest = {'name': name, 'original_archive_name': original_name,
                'source_id': (re.search(r'_(\d+)_texture', original_name).group(1)
                              if re.search(r'_(\d+)_texture', original_name) else previous.get('source_id')),
                'archive_path': renamed_archive.relative_to(project).as_posix(),
                'archive_sha256': archive_hash, 'files': [p[2] for p in planned]}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    assert digest(renamed_archive.read_bytes()) == archive_hash
    for output, _, record in planned:
        assert digest(output.read_bytes()) == record['sha256']
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('name')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = prepare(args.archive, args.name, args.destination)
    print(result['name'], ':', len(result['files']), 'verified source files')
