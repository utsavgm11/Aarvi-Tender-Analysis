import React, { useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { cityCoords } from '../../utils/geoData';

const TenderMap = ({ tenders }) => {

  // 1. Process and Aggregate Data
  const locationStats = useMemo(() => {
    const stats = {};

    // Ignore broad regions that can't be pinned to a single city
    const invalidLocations = [
      "pan india", "central", "nr", "south region",
      "west india", "india", "all india"
    ];

    tenders.forEach(t => {
      if (!t.location) return;

      // --- THE FIX: Clean the location string inside the loop ---
      // 1. Lowercase and ensure it's a string
      let rawLocation = String(t.location).toLowerCase().trim();
      
      // 2. Strip away dirty text like "kochi \n(imp to attend...)" or "Coimbatore / bengaluru"
      let cleanLocation = rawLocation.split('\n')[0].split('(')[0].split('/')[0].trim();

      // 3. Ignore invalid broad values
      if (invalidLocations.includes(cleanLocation)) return;

      // 4. Check if we have coordinates for this clean city name
      if (cityCoords[cleanLocation]) {
        // Increment the count for this city
        stats[cleanLocation] = (stats[cleanLocation] || 0) + 1;
      } 
      // Note: We silently ignore missing coordinates now to keep your console clean!
    });

    return stats;
  }, [tenders]);

  // 2. India center coordinates
  const indiaCenter = [20.5937, 78.9629];

  return (
    <div className="h-full w-full rounded-3xl overflow-hidden border border-slate-200 shadow-inner min-h-[400px]">
      <MapContainer
        center={indiaCenter}
        zoom={5}
        style={{ height: '100%', width: '100%', background: '#f8fafc' }}
        scrollWheelZoom={false}
      >
        {/* Clean Map Theme */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {Object.entries(locationStats).map(([city, count]) => {
          const position = cityCoords[city];

          // Capitalize the first letter for the beautiful tooltip display
          const displayCity = city.charAt(0).toUpperCase() + city.slice(1);

          return (
            <CircleMarker
              key={city}
              center={position}
              radius={Math.max(8, Math.min(count * 1.5, 40))}
              fillColor="#6366f1"
              color="#4338ca"
              weight={1.5}
              fillOpacity={0.5}
            >
              <Tooltip direction="top" offset={[0, -5]} opacity={1}>
                <div className="p-1">
                  <p className="font-black text-slate-800 text-xs uppercase">
                    {displayCity}
                  </p>
                  <p className="text-indigo-600 font-bold text-sm">
                    {count} {count === 1 ? 'Tender' : 'Tenders'}
                  </p>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default TenderMap;