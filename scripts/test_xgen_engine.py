"""Real XGEN streaming engine + this package + real selected ASR, no app server."""
import argparse
import asyncio
import io
import json
from pathlib import Path
import sys
import time
import urllib.request
import uuid
import wave

from xgen_audio import AudioPreprocessor


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-repo',type=Path,required=True)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--wav',type=Path,required=True)
    parser.add_argument('--backend',choices=['none','rnnoise'],default='none')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.model_repo.resolve()))
    # Avoid backend/__init__.py booting GPU/process-manager services in this probe.
    import types
    package=types.ModuleType('backend')
    package.__path__=[str(args.model_repo.resolve()/'backend')]
    sys.modules['backend']=package
    from backend.asr_streaming.stream_engine import SttStreamEngine
    with urllib.request.urlopen(args.base_url+'/models',timeout=20) as r:model=json.load(r)['data'][0]['id']
    with wave.open(str(args.wav)) as w:
        assert (w.getframerate(),w.getsampwidth(),w.getnchannels())==(16000,2,1)
        pcm=w.readframes(w.getnframes())
    calls=[];events=[]
    def post(audio):
        boundary=uuid.uuid4().hex
        body=b''
        for key,value in [('model',model),('language','ko')]:
            body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()+audio+f'\r\n--{boundary}--\r\n'.encode()
        request=urllib.request.Request(args.base_url+'/audio/transcriptions',data=body,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
        with urllib.request.urlopen(request,timeout=30) as r:return json.load(r)['text']
    async def transcribe(audio,*,prompt=''):
        text=await asyncio.to_thread(post,audio)
        calls.append({'bytes':len(audio),'text':text})
        return text
    async def emit(event):events.append(event)
    engine=SttStreamEngine(transcribe,emit,mode='partials',sample_rate=16000)
    start=time.perf_counter()
    try:
        with AudioPreprocessor(denoise=args.backend) as processor:
            for offset in range(0,len(pcm),2048):
                result=processor.push(pcm[offset:offset+2048])
                if result.pcm:await engine.push(result.pcm)
                await asyncio.sleep(max(0,(offset+2048)/32000-(time.perf_counter()-start)))
            result=processor.finish()
            if result.pcm:await engine.push(result.pcm)
            await engine.flush()
    finally:await engine.close()
    finals=[e for e in events if e.get('type')=='final']
    errors=[e for e in events if e.get('type')=='error']
    report={'backend':args.backend,'input':str(args.wav),'calls':calls,'events':events,'seconds':time.perf_counter()-start,'model':model}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    assert calls and finals and not errors,report
    print(json.dumps({'backend':args.backend,'calls':len(calls),'finals':finals,'errors':errors},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
