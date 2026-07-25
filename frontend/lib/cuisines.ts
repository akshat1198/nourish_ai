// Cuisine taxonomy — mirror of backend/app/core/cuisines.py CUISINE_TAXONOMY.
// Asian and Indian are separate top-level groups; the questionnaire drills into
// a group's common cuisines with a "Doesn't matter" escape that sends the parent
// id ("indian"), while specific picks send child ids ("indian/gujarati").

export interface CuisineNode {
  id: string;
  label: string;
  count?: number;          // live recipe count (from GET /v1/cuisines); absent in the fallback
  children?: CuisineNode[];
}

export const CUISINES: CuisineNode[] = [
  {
    id: "asian",
    label: "Asian",
    children: [
      { id: "asian/chinese", label: "Chinese" },
      { id: "asian/thai", label: "Thai" },
      { id: "asian/japanese", label: "Japanese" },
      { id: "asian/filipino", label: "Filipino" },
      { id: "asian/korean", label: "Korean" },
      { id: "asian/vietnamese", label: "Vietnamese" },
      { id: "asian/sri_lankan", label: "Sri Lankan" },
      { id: "asian/malaysian", label: "Malaysian" },
      { id: "asian/indonesian", label: "Indonesian" },
      { id: "asian/nepalese", label: "Nepalese" },
      { id: "asian/burmese", label: "Burmese" },
    ],
  },
  {
    id: "indian",
    label: "Indian",
    children: [
      { id: "indian/north_indian", label: "North Indian" },
      { id: "indian/south_indian", label: "South Indian" },
      { id: "indian/punjabi", label: "Punjabi" },
      { id: "indian/gujarati", label: "Gujarati" },
      { id: "indian/marathi", label: "Marathi" },
      { id: "indian/bengali", label: "Bengali" },
      { id: "indian/kerala", label: "Kerala" },
      { id: "indian/tamil_nadu", label: "Tamil Nadu" },
      { id: "indian/karnataka", label: "Karnataka" },
      { id: "indian/rajasthani", label: "Rajasthani" },
      { id: "indian/andhra", label: "Andhra" },
      { id: "indian/goan", label: "Goan" },
    ],
  },
  { id: "italian", label: "Italian" },
  { id: "mexican", label: "Mexican" },
  { id: "mediterranean", label: "Mediterranean" },
  { id: "middle-eastern", label: "Middle Eastern" },
  { id: "american", label: "American" },
  {
    id: "european",
    label: "European",
    children: [
      { id: "european/british", label: "British" },
      { id: "european/irish", label: "Irish" },
      { id: "european/french", label: "French" },
      { id: "european/spanish", label: "Spanish" },
      { id: "european/portuguese", label: "Portuguese" },
      { id: "european/dutch", label: "Dutch" },
      { id: "european/german", label: "German" },
      { id: "european/polish", label: "Polish" },
      { id: "european/russian", label: "Russian" },
      { id: "european/ukrainian", label: "Ukrainian" },
      { id: "european/croatian", label: "Croatian" },
      { id: "european/slovak", label: "Slovak" },
      { id: "european/norwegian", label: "Norwegian" },
    ],
  },
  {
    id: "latin-american",
    label: "Latin American",
    children: [
      { id: "latin-american/brazilian", label: "Brazilian" },
      { id: "latin-american/colombian", label: "Colombian" },
      { id: "latin-american/argentine", label: "Argentine" },
      { id: "latin-american/venezuelan", label: "Venezuelan" },
      { id: "latin-american/uruguayan", label: "Uruguayan" },
      { id: "latin-american/peruvian", label: "Peruvian" },
      { id: "latin-american/chilean", label: "Chilean" },
      { id: "latin-american/cuban", label: "Cuban" },
    ],
  },
  {
    id: "caribbean",
    label: "Caribbean",
    children: [
      { id: "caribbean/jamaican", label: "Jamaican" },
      { id: "caribbean/trinidadian", label: "Trinidadian" },
      { id: "caribbean/haitian", label: "Haitian" },
    ],
  },
  {
    id: "african",
    label: "African",
    children: [
      { id: "african/algerian", label: "Algerian" },
      { id: "african/kenyan", label: "Kenyan" },
      { id: "african/nigerian", label: "Nigerian" },
      { id: "african/ethiopian", label: "Ethiopian" },
      { id: "african/south_african", label: "South African" },
    ],
  },
];
