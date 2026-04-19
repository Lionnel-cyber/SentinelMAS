import type { Feature } from 'geojson';

export interface DisasterEvent extends Feature {
  properties: {
    id: string;
    title: string;
    disaster_type: string;
    severity_score: number;
    latitude: number;
    longitude: number;
    date: string;
    source: string;
  };
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
}

function calculateSeverity(event: any, type: string): number {
  if (type === 'earthquakes') {
    const magnitude = event.magnitude || 0;
    return Math.min(100, (magnitude / 9) * 100);
  }
  if (type === 'fires') {
    return 75;
  }
  return 50;
}

function getDisasterType(category: string, eventType?: string): string {
  const categoryMap: Record<string, string> = {
    earthquakes: 'earthquake',
    wildfires: 'fire',
    floods: 'flood',
    storms: 'storm',
    hurricanes: 'storm',
    volcanoes: 'volcano',
    tsunamis: 'tsunami',
  };
  return categoryMap[category?.toLowerCase()] || 'event';
}

export async function loadDisasterEvents(): Promise<DisasterEvent[]> {
  const events: DisasterEvent[] = [];

  try {
    const eonetResponse = await fetch('/data/raw/eonet_events.json');
    if (eonetResponse.ok) {
      const eonetData = await eonetResponse.json();
      for (const event of eonetData) {
        const disasterType = getDisasterType(event.category);
        events.push({
          type: 'Feature',
          id: event.event_id,
          properties: {
            id: event.event_id,
            title: event.title,
            disaster_type: disasterType,
            severity_score: 60,
            latitude: event.latitude,
            longitude: event.longitude,
            date: event.start_date,
            source: 'EONET',
          },
          geometry: {
            type: 'Point',
            coordinates: [event.longitude, event.latitude],
          },
        });
      }
    }
  } catch (error) {
    console.error('Failed to load EONET events:', error);
  }

  try {
    const usgsResponse = await fetch('/data/raw/usgs_earthquakes.json');
    if (usgsResponse.ok) {
      const usgsData = await usgsResponse.json();
      for (const quake of usgsData) {
        const severity = calculateSeverity(quake, 'earthquakes');
        events.push({
          type: 'Feature',
          id: quake.event_id,
          properties: {
            id: quake.event_id,
            title: `Magnitude ${quake.magnitude} - ${quake.place}`,
            disaster_type: 'earthquake',
            severity_score: severity,
            latitude: quake.latitude,
            longitude: quake.longitude,
            date: new Date(quake.time).toISOString(),
            source: 'USGS',
          },
          geometry: {
            type: 'Point',
            coordinates: [quake.longitude, quake.latitude],
          },
        });
      }
    }
  } catch (error) {
    console.error('Failed to load USGS earthquakes:', error);
  }

  return events;
}

export function getDisasterColor(disasterType: string): [number, number, number] {
  const colorMap: Record<string, [number, number, number]> = {
    earthquake: [255, 0, 0],
    fire: [255, 140, 0],
    flood: [0, 100, 255],
    storm: [128, 128, 128],
    hurricane: [128, 0, 128],
    volcano: [255, 69, 0],
    tsunami: [0, 149, 182],
    event: [200, 200, 200],
  };
  return colorMap[disasterType] || colorMap.event;
}

export function getSeverityRadius(severity: number): number {
  return Math.max(5000, (severity / 100) * 50000);
}
