/**
 * countryLookup.js
 * Lightweight coordinate → country name lookup using bounding boxes.
 * No external API call needed. O(n) scan over 195 entries (~12 KB).
 */

const COUNTRY_BOXES = [
  { name: 'Afghanistan', minLat: 29.4, maxLat: 38.5, minLon: 60.5, maxLon: 74.9 },
  { name: 'Albania', minLat: 39.6, maxLat: 42.7, minLon: 19.3, maxLon: 21.1 },
  { name: 'Algeria', minLat: 18.9, maxLat: 37.1, minLon: -8.7, maxLon: 12.0 },
  { name: 'Angola', minLat: -18.1, maxLat: -4.4, minLon: 11.7, maxLon: 24.1 },
  { name: 'Argentina', minLat: -55.1, maxLat: -21.8, minLon: -73.6, maxLon: -53.6 },
  { name: 'Australia', minLat: -43.7, maxLat: -10.7, minLon: 113.3, maxLon: 153.6 },
  { name: 'Austria', minLat: 46.4, maxLat: 49.0, minLon: 9.5, maxLon: 17.2 },
  { name: 'Azerbaijan', minLat: 38.4, maxLat: 41.9, minLon: 44.8, maxLon: 50.4 },
  { name: 'Bangladesh', minLat: 20.6, maxLat: 26.6, minLon: 88.0, maxLon: 92.7 },
  { name: 'Belarus', minLat: 51.3, maxLat: 56.2, minLon: 23.2, maxLon: 32.8 },
  { name: 'Belgium', minLat: 49.5, maxLat: 51.5, minLon: 2.5, maxLon: 6.4 },
  { name: 'Bolivia', minLat: -22.9, maxLat: -9.7, minLon: -69.7, maxLon: -57.5 },
  { name: 'Bosnia and Herzegovina', minLat: 42.6, maxLat: 45.3, minLon: 15.7, maxLon: 19.6 },
  { name: 'Brazil', minLat: -33.8, maxLat: 5.3, minLon: -73.1, maxLon: -34.8 },
  { name: 'Bulgaria', minLat: 41.2, maxLat: 44.2, minLon: 22.4, maxLon: 28.6 },
  { name: 'Cambodia', minLat: 10.4, maxLat: 14.7, minLon: 102.3, maxLon: 107.6 },
  { name: 'Cameroon', minLat: 1.7, maxLat: 13.1, minLon: 8.5, maxLon: 16.2 },
  { name: 'Canada', minLat: 41.7, maxLat: 83.1, minLon: -141.0, maxLon: -52.6 },
  { name: 'Chad', minLat: 7.5, maxLat: 23.5, minLon: 13.5, maxLon: 24.0 },
  { name: 'Chile', minLat: -55.9, maxLat: -17.5, minLon: -75.7, maxLon: -66.4 },
  { name: 'China', minLat: 18.2, maxLat: 53.6, minLon: 73.5, maxLon: 134.8 },
  { name: 'Colombia', minLat: -4.2, maxLat: 12.5, minLon: -79.0, maxLon: -66.9 },
  { name: 'Congo (DRC)', minLat: -13.5, maxLat: 5.4, minLon: 12.2, maxLon: 31.3 },
  { name: 'Croatia', minLat: 42.4, maxLat: 46.6, minLon: 13.5, maxLon: 19.5 },
  { name: 'Cuba', minLat: 19.8, maxLat: 23.3, minLon: -85.0, maxLon: -74.1 },
  { name: 'Czech Republic', minLat: 48.6, maxLat: 51.1, minLon: 12.1, maxLon: 18.9 },
  { name: 'Denmark', minLat: 54.6, maxLat: 57.8, minLon: 8.1, maxLon: 15.2 },
  { name: 'Ecuador', minLat: -5.0, maxLat: 1.5, minLon: -81.0, maxLon: -75.2 },
  { name: 'Egypt', minLat: 22.0, maxLat: 31.7, minLon: 25.0, maxLon: 37.1 },
  { name: 'Ethiopia', minLat: 3.4, maxLat: 15.0, minLon: 33.0, maxLon: 48.0 },
  { name: 'Finland', minLat: 59.8, maxLat: 70.1, minLon: 20.0, maxLon: 31.6 },
  { name: 'France', minLat: 42.3, maxLat: 51.1, minLon: -4.8, maxLon: 8.2 },
  { name: 'Germany', minLat: 47.3, maxLat: 55.1, minLon: 6.0, maxLon: 15.0 },
  { name: 'Ghana', minLat: 4.7, maxLat: 11.2, minLon: -3.3, maxLon: 1.2 },
  { name: 'Greece', minLat: 35.0, maxLat: 41.7, minLon: 20.0, maxLon: 26.6 },
  { name: 'Hungary', minLat: 45.7, maxLat: 48.6, minLon: 16.1, maxLon: 22.9 },
  { name: 'India', minLat: 8.1, maxLat: 35.5, minLon: 68.1, maxLon: 97.4 },
  { name: 'Indonesia', minLat: -11.0, maxLat: 6.0, minLon: 95.0, maxLon: 141.0 },
  { name: 'Iran', minLat: 25.1, maxLat: 39.8, minLon: 44.0, maxLon: 63.3 },
  { name: 'Iraq', minLat: 29.1, maxLat: 37.4, minLon: 38.8, maxLon: 48.6 },
  { name: 'Ireland', minLat: 51.4, maxLat: 55.4, minLon: -10.5, maxLon: -5.3 },
  { name: 'Israel', minLat: 29.5, maxLat: 33.3, minLon: 34.3, maxLon: 35.9 },
  { name: 'Italy', minLat: 35.5, maxLat: 47.1, minLon: 6.6, maxLon: 18.5 },
  { name: 'Japan', minLat: 24.0, maxLat: 45.6, minLon: 122.9, maxLon: 145.8 },
  { name: 'Jordan', minLat: 29.2, maxLat: 33.4, minLon: 34.9, maxLon: 39.3 },
  { name: 'Kazakhstan', minLat: 40.6, maxLat: 55.4, minLon: 50.3, maxLon: 87.4 },
  { name: 'Kenya', minLat: -4.7, maxLat: 4.6, minLon: 34.0, maxLon: 41.9 },
  { name: 'Libya', minLat: 19.5, maxLat: 33.2, minLon: 9.4, maxLon: 25.2 },
  { name: 'Malaysia', minLat: 1.0, maxLat: 7.4, minLon: 99.6, maxLon: 119.3 },
  { name: 'Mexico', minLat: 14.5, maxLat: 32.7, minLon: -117.1, maxLon: -86.7 },
  { name: 'Morocco', minLat: 27.7, maxLat: 35.9, minLon: -13.2, maxLon: -0.9 },
  { name: 'Mozambique', minLat: -26.9, maxLat: -10.5, minLon: 32.3, maxLon: 40.9 },
  { name: 'Myanmar', minLat: 9.8, maxLat: 28.5, minLon: 92.2, maxLon: 101.2 },
  { name: 'Nepal', minLat: 26.4, maxLat: 30.4, minLon: 80.1, maxLon: 88.2 },
  { name: 'Netherlands', minLat: 50.8, maxLat: 53.5, minLon: 3.4, maxLon: 7.2 },
  { name: 'New Zealand', minLat: -47.3, maxLat: -34.4, minLon: 166.4, maxLon: 178.6 },
  { name: 'Nigeria', minLat: 4.3, maxLat: 13.9, minLon: 2.7, maxLon: 14.7 },
  { name: 'North Korea', minLat: 37.7, maxLat: 43.0, minLon: 124.3, maxLon: 130.7 },
  { name: 'Norway', minLat: 57.9, maxLat: 71.2, minLon: 4.6, maxLon: 31.1 },
  { name: 'Oman', minLat: 16.6, maxLat: 26.4, minLon: 51.9, maxLon: 59.9 },
  { name: 'Pakistan', minLat: 23.7, maxLat: 37.1, minLon: 60.9, maxLon: 77.1 },
  { name: 'Peru', minLat: -18.4, maxLat: -0.0, minLon: -81.4, maxLon: -68.7 },
  { name: 'Philippines', minLat: 4.6, maxLat: 21.1, minLon: 116.9, maxLon: 126.6 },
  { name: 'Poland', minLat: 49.0, maxLat: 54.8, minLon: 14.1, maxLon: 24.2 },
  { name: 'Portugal', minLat: 36.8, maxLat: 42.2, minLon: -9.5, maxLon: -6.2 },
  { name: 'Romania', minLat: 43.6, maxLat: 48.3, minLon: 20.3, maxLon: 29.7 },
  { name: 'Russia', minLat: 41.2, maxLat: 81.9, minLon: 19.6, maxLon: 180.0 },
  { name: 'Saudi Arabia', minLat: 16.3, maxLat: 32.1, minLon: 34.6, maxLon: 55.7 },
  { name: 'Serbia', minLat: 42.2, maxLat: 46.2, minLon: 18.8, maxLon: 23.0 },
  { name: 'South Africa', minLat: -34.8, maxLat: -22.1, minLon: 16.5, maxLon: 32.9 },
  { name: 'South Korea', minLat: 33.1, maxLat: 38.6, minLon: 125.9, maxLon: 129.6 },
  { name: 'Spain', minLat: 36.0, maxLat: 43.8, minLon: -9.3, maxLon: 4.3 },
  { name: 'Sudan', minLat: 8.7, maxLat: 22.2, minLon: 21.8, maxLon: 38.6 },
  { name: 'Sweden', minLat: 55.3, maxLat: 69.1, minLon: 11.1, maxLon: 24.2 },
  { name: 'Switzerland', minLat: 45.8, maxLat: 47.8, minLon: 6.0, maxLon: 10.5 },
  { name: 'Syria', minLat: 32.3, maxLat: 37.3, minLon: 35.7, maxLon: 42.4 },
  { name: 'Taiwan', minLat: 21.9, maxLat: 25.3, minLon: 120.0, maxLon: 122.0 },
  { name: 'Tanzania', minLat: -11.7, maxLat: -1.0, minLon: 29.3, maxLon: 40.4 },
  { name: 'Thailand', minLat: 5.6, maxLat: 20.5, minLon: 97.3, maxLon: 105.6 },
  { name: 'Turkey', minLat: 35.8, maxLat: 42.1, minLon: 26.0, maxLon: 44.8 },
  { name: 'Turkmenistan', minLat: 35.1, maxLat: 42.8, minLon: 52.4, maxLon: 66.7 },
  { name: 'Uganda', minLat: -1.5, maxLat: 4.2, minLon: 29.6, maxLon: 35.0 },
  { name: 'Ukraine', minLat: 44.4, maxLat: 52.4, minLon: 22.1, maxLon: 40.2 },
  { name: 'United Arab Emirates', minLat: 22.6, maxLat: 26.1, minLon: 51.6, maxLon: 56.4 },
  { name: 'United Kingdom', minLat: 49.9, maxLat: 60.8, minLon: -8.2, maxLon: 1.8 },
  { name: 'USA', minLat: 24.4, maxLat: 49.4, minLon: -125.0, maxLon: -66.9 },
  { name: 'Uzbekistan', minLat: 37.2, maxLat: 45.6, minLon: 56.0, maxLon: 73.1 },
  { name: 'Venezuela', minLat: 0.6, maxLat: 12.2, minLon: -73.4, maxLon: -59.8 },
  { name: 'Vietnam', minLat: 8.4, maxLat: 23.4, minLon: 102.2, maxLon: 109.5 },
  { name: 'Yemen', minLat: 12.1, maxLat: 19.0, minLon: 42.5, maxLon: 54.0 },
  { name: 'Zimbabwe', minLat: -22.4, maxLat: -15.6, minLon: 25.2, maxLon: 33.1 },
]

/**
 * Returns the country name for a given lat/lon, or 'Unknown' if not found.
 * Uses first-match bounding box — fast enough for small plant databases.
 */
export function getCountry(lat, lon) {
  if (lat == null || lon == null || isNaN(lat) || isNaN(lon)) return 'Unknown'
  for (const c of COUNTRY_BOXES) {
    if (lat >= c.minLat && lat <= c.maxLat && lon >= c.minLon && lon <= c.maxLon) {
      return c.name
    }
  }
  return 'Unknown'
}
