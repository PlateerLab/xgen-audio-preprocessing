"""Compare saved benchmark WAVs against an explicitly selected OpenAI-style ASR."""
import argparse
import json
from pathlib import Path
import time
import urllib.request
import uuid

from benchmark import cer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    with urllib.request.urlopen(base+'/models', timeout=20) as response:
        model = json.load(response)['data'][0]['id']
    rows = []
    for file in sorted(args.benchmark.glob('korean_*.wav')):
        boundary = uuid.uuid4().hex
        body = b''
        for key, value in [('model',model),('language','ko')]:
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()+file.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request(base+'/audio/transcriptions', data=body, headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                text=json.load(response)['text']
            row={'file':file.name,'text':text,'cer':cer('안녕하세요. 오늘 날씨가 정말 좋네요.',text),'seconds':time.perf_counter()-start}
        except Exception as error:
            row={'file':file.name,'error':str(error)}
        rows.append(row)
        args.output.write_text(json.dumps({'base_url':base,'model':model,'rows':rows},ensure_ascii=False,indent=2))
        print(json.dumps(row,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
