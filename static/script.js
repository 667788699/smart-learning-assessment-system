const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => { video.srcObject = stream; });

// 每 5 秒擷取一張影像並送到後端
setInterval(() => {
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const imageData = canvas.toDataURL('image/jpeg');

  fetch('/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageData })
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('result').innerText = `情緒：${data.label}`;
  });
}, 5000);

function downloadPDF() {
  window.open('/export', '_blank');
}