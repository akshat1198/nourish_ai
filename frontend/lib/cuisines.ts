// Cuisine taxonomy — mirror of backend/app/core/cuisines.py CUISINE_TAXONOMY.
// Asian and Indian are separate top-level groups; the questionnaire drills into
// a group's common cuisines with a "Doesn't matter" escape that sends the parent
// id ("indian"), while specific picks send child ids ("indian/gujarati").

export interface CuisineNode {
  id: string;
  label: string;
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
    ],
  },
  {
    id: "indian",
    label: "Indian",
    children: [
      { id: "indian/north_indian", label: "North Indian" },
      { id: "indian/south_indian", label: "South Indian" },
      { id: "indian/gujarati", label: "Gujarati" },
      { id: "indian/punjabi", label: "Punjabi" },
      { id: "indian/marathi", label: "Marathi" },
      { id: "indian/bengali", label: "Bengali" },
    ],
  },
  { id: "italian", label: "Italian" },
  { id: "mexican", label: "Mexican" },
  { id: "mediterranean", label: "Mediterranean" },
  { id: "middle-eastern", label: "Middle Eastern" },
  { id: "american", label: "American" },
];
