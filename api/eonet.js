import { writeFileSync, mkdirSync } from 'fs';

const EONET_URL = 'https://eonet.gsfc.nasa.gov/api/v3/events';

async function fetchEONETEvents() {
  try {
    console.log('Fetching EONET events from:', EONET_URL);
    const response = await fetch(EONET_URL);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    console.log(`Found ${data.events.length} events, processing...`);

    const events = [];
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

    mkdirSync('data/raw', { recursive: true });
    writeFileSync(
      'data/raw/eonet_events.json',
      JSON.stringify(events, null, 2),
    );

    console.log(`Fetched ${events.length} EONET events`);
    return events.length;
  } catch (error) {
    console.error('Error fetching EONET events:', error.message);
    throw error;
  }
}

// Run if executed directly
if (process.argv[1]?.endsWith('eonet.js')) {
  fetchEONETEvents()
    .then((count) => {
      console.log(`Fetched ${count} EONET events`);
      process.exit(0);
    })
    .catch((error) => {
      console.error('Failed:', error.message);
      process.exit(1);
    });
}

export { fetchEONETEvents };
