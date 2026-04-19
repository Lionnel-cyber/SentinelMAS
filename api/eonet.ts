import { writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';

const EONET_URL = 'https://eonet.gsfc.nasa.gov/api/v3/events';

interface EONETGeometry {
  type: string;
  coordinates: [number, number];
  date?: string;
}

interface EONETCategory {
  id: string;
  title: string;
}

interface EONETSource {
  id: string;
  url: string;
}

interface EONETEventRaw {
  id: string;
  title: string;
  description: string;
  link: string;
  categories: EONETCategory[];
  geometry: EONETGeometry[];
  sources: EONETSource[];
  closed?: string;
}

interface EONETEventProcessed {
  event_id: string;
  title: string;
  category: string;
  latitude: number;
  longitude: number;
  start_date: string;
  sources: EONETSource[];
}

async function fetchEONETEvents(): Promise<number> {
  try {
    const response = await fetch(EONET_URL);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = (await response.json()) as { events: EONETEventRaw[] };
    const events: EONETEventProcessed[] = [];

    for (const event of data.events) {
      if (event.geometry && event.geometry.length > 0) {
        const geo = event.geometry[event.geometry.length - 1];
        events.push({
          event_id: event.id,
          title: event.title,
          category: event.categories[0]?.id || 'unknown',
          latitude: geo.coordinates[1],
          longitude: geo.coordinates[0],
          start_date: geo.date || event.closed || '',
          sources: event.sources || [],
        });
      }
    }

    const rawDir = 'data/raw';
    mkdirSync(rawDir, { recursive: true });
    writeFileSync(
      `${rawDir}/eonet_events.json`,
      JSON.stringify(events, null, 2),
    );

    return events.length;
  } catch (error) {
    console.error('Error fetching EONET events:', error);
    throw error;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchEONETEvents()
    .then((count) => {
      console.log(`Fetched ${count} EONET events`);
      process.exit(0);
    })
    .catch((error) => {
      console.error('Failed:', error);
      process.exit(1);
    });
}

export { fetchEONETEvents, EONETEventProcessed };
