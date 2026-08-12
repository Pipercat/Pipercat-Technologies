const RAD = Math.PI / 180;

function solarError(message) { return Object.assign(new Error(message), { code: 'LOCATION_INVALID' }); }
function validateLocation(input) {
  const latitude = Number(input?.latitude), longitude = Number(input?.longitude);
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude) || longitude < -180 || longitude > 180) throw solarError('Breiten- oder Längengrad ist ungültig.');
  return { latitude: Math.round(latitude * 100000) / 100000, longitude: Math.round(longitude * 100000) / 100000 };
}

function dayOfYear(date) { const start = new Date(Date.UTC(date.getUTCFullYear(), 0, 0)); return Math.floor((Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) - start) / 86400000); }
function normalizeDegrees(value) { return ((value % 360) + 360) % 360; }

function calculateUtcHour(date, latitude, longitude, sunrise) {
  const n = dayOfYear(date), lngHour = longitude / 15, approximate = n + ((sunrise ? 6 : 18) - lngHour) / 24;
  const meanAnomaly = (0.9856 * approximate) - 3.289;
  let trueLongitude = meanAnomaly + 1.916 * Math.sin(meanAnomaly * RAD) + 0.020 * Math.sin(2 * meanAnomaly * RAD) + 282.634;
  trueLongitude = normalizeDegrees(trueLongitude);
  let rightAscension = Math.atan(0.91764 * Math.tan(trueLongitude * RAD)) / RAD;
  rightAscension = normalizeDegrees(rightAscension);
  rightAscension += Math.floor(trueLongitude / 90) * 90 - Math.floor(rightAscension / 90) * 90;
  rightAscension /= 15;
  const sinDeclination = 0.39782 * Math.sin(trueLongitude * RAD);
  const cosDeclination = Math.cos(Math.asin(sinDeclination));
  const cosHour = (Math.cos(90.833 * RAD) - sinDeclination * Math.sin(latitude * RAD)) / (cosDeclination * Math.cos(latitude * RAD));
  if (cosHour > 1 || cosHour < -1) return null;
  const hourAngle = (sunrise ? 360 - Math.acos(cosHour) / RAD : Math.acos(cosHour) / RAD) / 15;
  const localMeanTime = hourAngle + rightAscension - 0.06571 * approximate - 6.622;
  return ((localMeanTime - lngHour) % 24 + 24) % 24;
}

function hourToDate(date, hour) {
  if (hour === null) return null;
  const midnight = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  return new Date(midnight + Math.round(hour * 3600000));
}

function calculateSolarEvents(date, location) {
  const { latitude, longitude } = validateLocation(location);
  return { sunrise: hourToDate(date, calculateUtcHour(date, latitude, longitude, true)), sunset: hourToDate(date, calculateUtcHour(date, latitude, longitude, false)) };
}

module.exports = { validateLocation, calculateSolarEvents };
