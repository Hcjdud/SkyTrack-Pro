// Дополнительные функции для карты
let animationFrame;
let lastUpdate = Date.now();

// Анимация маркеров
function animateMarkers() {
    const now = Date.now();
    const delta = now - lastUpdate;
    
    if (delta > 50) { // Обновление 20 fps
        markers.forEach((marker, id) => {
            // Добавляем пульсацию
            const scale = 1 + Math.sin(now * 0.005) * 0.1;
            marker.setIcon({
                ...marker.getIcon(),
                scale: 8 * scale
            });
        });
        lastUpdate = now;
    }
    
    animationFrame = requestAnimationFrame(animateMarkers);
}

// Запускаем анимацию после инициализации
setTimeout(() => {
    animateMarkers();
}, 1000);

// Эффект следа
function drawTrail(flight, map) {
    if (!flight.track || flight.track.length < 2) return;
    
    const trail = new google.maps.Polyline({
        path: flight.track.map(p => ({ lat: p.lat, lng: p.lon })),
        geodesic: true,
        strokeColor: getColorByAltitude(flight.altitude),
        strokeOpacity: 0.6,
        strokeWeight: 2
    });
    
    trail.setMap(map);
    return trail;
}
