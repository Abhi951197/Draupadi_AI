// Initialize the map once the DOM content has loaded
document.addEventListener("DOMContentLoaded", () => {
    const map = L.map('map', {
        zoomControl: false // Disable default zoom control to avoid overlapping the button
    }).setView([19.076, 72.8777], 12); // Centered on Mumbai

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
    }).addTo(map);

    // Example marker
    const marker = L.marker([19.076, 72.8777]).addTo(map)
        .bindPopup('Mumbai')
        .openPopup();

    // Event listeners for buttons
    document.getElementById('emergencyButton').addEventListener('click', () => {
        alert('Emergency Alert Triggered!');
    });

    document.getElementById('safeButton').addEventListener('click', () => {
        alert('You are now in Safe Mode.');
    });
});
