import { useEffect, type ReactNode } from "react";
import { CircleMarker, LayersControl, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L, { type LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import icon from "leaflet/dist/images/marker-icon.png";
import icon2x from "leaflet/dist/images/marker-icon-2x.png";
import shadow from "leaflet/dist/images/marker-shadow.png";

// Vite-friendly default marker icons
L.Icon.Default.mergeOptions({ iconUrl: icon, iconRetinaUrl: icon2x, shadowUrl: shadow });

export function BaseMap({ children, height = 460, center = [22.2, 73.2], zoom = 10, scroll = false }:
  { children?: ReactNode; height?: number; center?: LatLngExpression; zoom?: number; scroll?: boolean }) {
  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom={scroll} className="map" style={{ height }}>
      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="Street map">
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" maxZoom={19} />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Satellite">
          <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics" maxZoom={19} />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Light">
          <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution="&copy; OpenStreetMap contributors &copy; CARTO" maxZoom={19} />
        </LayersControl.BaseLayer>
      </LayersControl>
      {children}
    </MapContainer>
  );
}

export function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.length ? `${points[0]}|${points[points.length - 1]}|${points.length}` : "";
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [20, 20] });
    else if (points.length === 1) map.setView(points[0], 15);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

export function AssetShape({ a, color, weight = 6, children }: {
  a: { type: string; geometry?: [number, number][] | null; lat: number | null; lng: number | null };
  color: string; weight?: number; children?: ReactNode;
}) {
  if (a.geometry && a.geometry.length) {
    return <Polyline positions={a.geometry} pathOptions={{ color, weight, opacity: 0.9 }}>{children && <Popup>{children}</Popup>}</Polyline>;
  }
  if (a.lat !== null && a.lng !== null) {
    const r = a.type === "bridge" ? 9 : a.type === "building" ? 8 : 6;
    return (
      <CircleMarker center={[a.lat, a.lng]} radius={r} pathOptions={{ color: "#fff", weight: 2, fillColor: color, fillOpacity: 1 }}>
        {children && <Popup>{children}</Popup>}
      </CircleMarker>
    );
  }
  return null;
}
