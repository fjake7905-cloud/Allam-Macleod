#!/usr/bin/env python3
"""Temporary, capability-link PDF upload portal; standard library only.
Run with python upload_server.py. Source PDFs are never served for download.
"""
import json
import os
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

UPLOADS = Path('/home/user/uploads')
STATE = Path('/home/user/.local/clinical-upload')
STATE.mkdir(parents=True, exist_ok=True)
TOKEN_FILE = STATE / 'token'
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(24))
    TOKEN_FILE.chmod(0o600)
TOKEN = TOKEN_FILE.read_text().strip()
PREFIX = '/upload/' + TOKEN
FILES = ('allam.pdf', 'Macleod_examination.pdf', 'Macleod_diagnosis.pdf')
MAX_BYTES = 150 * 1024 * 1024
LOCK = threading.Lock()

PAGE = '''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>رفع المراجع الطبية</title><style>
*{box-sizing:border-box}body{margin:0;background:#fdfbf7;color:#29343a;font-family:system-ui,sans-serif;line-height:1.8}main{max-width:850px;margin:55px auto;padding:24px}h1{color:#8B4513;margin:0}small,.muted{color:#617078}.intro{margin-bottom:26px}.notice{background:#fff0e2;border-right:4px solid #b76c21;padding:16px;border-radius:8px}article{background:white;border:1px solid #e0e3e4;border-radius:14px;padding:24px;margin:18px 0;box-shadow:0 6px 22px #00000005}h2{font-size:20px;margin:0 0 12px}input{display:block;width:100%;padding:12px;background:#f4f6f7;border-radius:8px;margin:12px 0}button{border:0;border-radius:8px;background:#0056b3;color:white;padding:12px 25px;font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:wait}progress{width:100%;height:12px;accent-color:#0056b3}.status{font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere}.ok{color:#166534}.error{color:#b42318}#summary{font-weight:600;padding:16px;background:#f0f8ff;border-radius:10px}footer{margin-top:28px;font-size:14px}code{direction:ltr;unicode-bidi:embed}
</style></head><body><main><small>CLINICAL NOTES · SOURCE UPLOAD</small><h1>رفع المراجع الطبية</h1>
<p class="intro">ارفع الملفات الثلاثة كلًّا على حدة. لا تحتاج إلى ZIP أو حساب سحابي. اختر الملف الصحيح في الخانة المطابقة ثم اضغط «رفع الملف».</p>
<div class="notice">صفحة مؤقتة مرتبطة بهذه الجلسة، وليست خدمة تخزين سحابية دائمة. لا تشارك رابطها ولا ترفع بيانات مرضى أو معلومات شخصية حساسة. لا تغلق الصفحة أثناء الرفع.</div>
<div id="cards"></div><p id="summary" role="status">جارٍ التحقق من الملفات…</p>
<footer>بعد اكتمال الرفع ارجع إلى المحادثة واكتب <strong>«تم الرفع»</strong> لأبدأ الاستخراج والدمج. رفع الملفات وحده لا يبدأ المعالجة تلقائيًا.</footer>
</main><script>
const base=__PREFIX__, names=['allam.pdf','Macleod_examination.pdf','Macleod_diagnosis.pdf'];
const titles=['مرجع علّام — Allam','مرجع الفحص السريري — Macleod Examination','مرجع التشخيص — Macleod Diagnosis'];
let stored={};
const cards=document.getElementById('cards');
names.forEach((name,i)=>{
 const el=document.createElement('article');
 el.innerHTML=`<h2>${i+1}. ${titles[i]}</h2><small>سيُحفظ باسم <code>${name}</code> · الحد الأقصى 150 MB</small><input type="file" accept=".pdf,application/pdf" aria-label="${titles[i]}"><button type="button">رفع الملف</button><p class="status" role="status">لم يُرفع بعد</p><progress max="100" value="0" hidden></progress>`;
 const input=el.querySelector('input'),button=el.querySelector('button'),status=el.querySelector('.status'),progress=el.querySelector('progress');
 el.dataset.name=name;
 button.onclick=()=>{
  const file=input.files[0];
  if(!file){status.textContent='اختر ملف PDF أولًا.';return;}
  if(file.size>150*1024*1024){status.textContent='الملف أكبر من 150 MB.';return;}
  if(!file.name.toLowerCase().endsWith('.pdf')){status.textContent='اختر ملفًا بصيغة PDF.';return;}
  if(stored[name]&&!confirm('هذا المرجع موجود. هل تريد استبداله بالملف المحدد؟'))return;
  const xhr=new XMLHttpRequest();
  xhr.open('POST',base+'/files/'+name);xhr.setRequestHeader('Content-Type','application/pdf');xhr.timeout=1800000;
  button.disabled=true;input.disabled=true;progress.hidden=false;progress.value=0;status.className='status';status.textContent='جارٍ رفع الملف…';
  xhr.upload.onprogress=e=>{if(e.lengthComputable){progress.value=e.loaded/e.total*100;status.textContent='جارٍ الرفع: '+Math.round(progress.value)+'%';}};
  const finish=()=>{button.disabled=false;input.disabled=false;};
  xhr.onload=async()=>{finish();let body;try{body=JSON.parse(xhr.responseText);}catch{body={error:'لم يستجب الخادم بصورة صحيحة. أعد المحاولة.'};}
   if(xhr.status===200){status.className='status ok';status.textContent='تم الرفع بنجاح.';progress.value=100;await refresh();}
   else{status.className='status error';status.textContent=body.error||'تعذّر الرفع.';}
  };
  xhr.onerror=xhr.ontimeout=()=>{finish();status.className='status error';status.textContent='انقطع الاتصال أو انتهت المهلة. أعد المحاولة.';};
  xhr.send(file);
 };
 cards.appendChild(el);
});
async function refresh(){
 try{const r=await fetch(base+'/status',{cache:'no-store'});if(!r.ok)throw Error();stored=await r.json();
 let count=0;names.forEach(name=>{if(stored[name]){count++;const el=[...cards.children].find(e=>e.dataset.name===name);const s=el.querySelector('.status');s.className='status ok';s.textContent='موجود في مساحة العمل · '+(stored[name]/1024/1024).toFixed(2)+' MB';}});
 document.getElementById('summary').textContent=count===3?'اكتمل وصول المراجع الثلاثة. ارجع للمحادثة واكتب «تم الرفع».':`وصل ${count} من 3 ملفات.`;
 }catch{document.getElementById('summary').textContent='تعذّر التحقق من الخادم. حدّث الصفحة أو ارجع للمحادثة.';}
}
refresh();
</script></body></html>'''.replace('__PREFIX__', json.dumps(PREFIX))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Do not log the private capability URL.
        print(f'{self.command}: request completed', flush=True)

    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False)
        body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path.rstrip('/')
        if path == PREFIX:
            self.respond(200, PAGE, 'text/html; charset=utf-8')
        elif path == PREFIX + '/status':
            self.respond(200, {n: (UPLOADS/n).stat().st_size if (UPLOADS/n).is_file() else 0 for n in FILES})
        elif path == '':
            self.respond(200, '<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>رفع المراجع</title><p>افتح رابط الرفع الخاص الذي أرسلته لك في المحادثة.</p></html>', 'text/html; charset=utf-8')
        else:
            self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        path = urlsplit(self.path).path
        valid = {PREFIX + '/files/' + name: name for name in FILES}
        if path not in valid:
            self.respond(404, {'error': 'Not found'})
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            size = 0
        if not 8 <= size <= MAX_BYTES:
            self.respond(413, {'error': 'حجم غير صالح. الحد الأقصى 150 MB.'})
            return
        if not LOCK.acquire(blocking=False):
            self.respond(409, {'error': 'يوجد رفع قيد التنفيذ. انتظر اكتماله ثم أعد المحاولة.'})
            return
        temp_path = None
        try:
            self.connection.settimeout(120)
            UPLOADS.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=UPLOADS, prefix='.upload-', delete=False) as out:
                temp_path = Path(out.name)
                remaining = size
                first = True
                while remaining:
                    chunk = self.rfile.read(min(1024*1024, remaining))
                    if not chunk:
                        raise ValueError('الرفع غير مكتمل. أعد المحاولة.')
                    if first and b'%PDF-' not in chunk[:1024]:
                        raise ValueError('الملف لا يحتوي على ترويسة PDF صالحة.')
                    first = False
                    out.write(chunk)
                    remaining -= len(chunk)
            os.replace(temp_path, UPLOADS/valid[path])
            self.respond(200, {'ok': True, 'name': valid[path], 'bytes': size})
        except (OSError, ValueError) as exc:
            self.respond(400, {'error': str(exc)})
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            LOCK.release()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    print(f'Upload portal listening on 0.0.0.0:{port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
