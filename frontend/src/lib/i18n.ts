// Citizen-facing strings in English, Gujarati and Hindi.
export type Lang = "en" | "gu" | "hi";

export const ISSUE_ICONS: Record<string, string> = {
  pothole: "🕳️", crack: "🧱", waterlogging: "🌊", signage: "🚸", railing: "🚧", leakage: "💧", other: "✏️",
};

export const T: Record<Lang, Record<string, any>> = {
  en: {
    brand: "Report a road problem", where: "Where is the problem?", useloc: "Use my location", tap: "or tap on the map",
    pinned: "Location selected ✓", what: "What is the problem?", details: "Photo & details (optional)", photo: "Add a photo",
    desc: "Describe the problem", phone: "Mobile number (for updates)", submit: "Submit report",
    nologin: "No login needed · Your report goes straight to the R&B engineer", thanks: "Thank you! Your ticket number",
    merged: "Others have already reported this — your report was added and raises its priority.", track: "Track status",
    another: "Report another problem", needpin: "Please mark the location on the map.", needissue: "Please choose the problem type.",
    liable: (c: string) => `Good news: this road is still under guarantee. ${c}, the contractor who built it, must repair it at no cost to the public.`,
    sending: "Sending…", locating: "Finding your location…", noloc: "Could not get your location — please tap on the map.",
    issues: { pothole: "Pothole", crack: "Cracks / broken road", waterlogging: "Waterlogging", signage: "Damaged sign", railing: "Broken railing", leakage: "Building leakage", other: "Other" },
  },
  gu: {
    brand: "રસ્તાની સમસ્યા જણાવો", where: "સમસ્યા ક્યાં છે?", useloc: "મારું સ્થાન વાપરો", tap: "અથવા નકશા પર ટેપ કરો",
    pinned: "સ્થાન પસંદ થયું ✓", what: "સમસ્યા શું છે?", details: "ફોટો અને વિગત (વૈકલ્પિક)", photo: "ફોટો ઉમેરો",
    desc: "સમસ્યાનું વર્ણન લખો", phone: "મોબાઇલ નંબર (અપડેટ માટે)", submit: "ફરિયાદ મોકલો",
    nologin: "લૉગિનની જરૂર નથી · તમારી ફરિયાદ સીધી માર્ગ અને મકાન વિભાગના ઇજનેર પાસે જાય છે", thanks: "આભાર! તમારો ટિકિટ નંબર",
    merged: "આ સમસ્યા પહેલેથી નોંધાયેલી છે — તમારી ફરિયાદ ઉમેરવામાં આવી છે અને તેની પ્રાથમિકતા વધી છે.", track: "સ્થિતિ જુઓ",
    another: "બીજી સમસ્યા જણાવો", needpin: "કૃપા કરીને નકશા પર સ્થાન પસંદ કરો.", needissue: "કૃપા કરીને સમસ્યાનો પ્રકાર પસંદ કરો.",
    liable: (c: string) => `સારા સમાચાર: આ રસ્તો હજી ગેરંટી હેઠળ છે. તેને બનાવનાર કોન્ટ્રાક્ટર ${c} એ તેને જનતાના કોઈ ખર્ચ વગર સુધારવો પડશે.`,
    sending: "મોકલી રહ્યા છીએ…", locating: "તમારું સ્થાન શોધી રહ્યા છીએ…", noloc: "સ્થાન મળ્યું નહીં — કૃપા કરીને નકશા પર ટેપ કરો.",
    issues: { pothole: "ખાડો", crack: "તિરાડ / તૂટેલો રસ્તો", waterlogging: "પાણી ભરાવું", signage: "તૂટેલું બોર્ડ", railing: "તૂટેલી રેલિંગ", leakage: "ઇમારતમાં લીકેજ", other: "અન્ય" },
  },
  hi: {
    brand: "सड़क की समस्या बताएं", where: "समस्या कहाँ है?", useloc: "मेरी लोकेशन इस्तेमाल करें", tap: "या नक्शे पर टैप करें",
    pinned: "स्थान चुना गया ✓", what: "समस्या क्या है?", details: "फोटो और विवरण (वैकल्पिक)", photo: "फोटो जोड़ें",
    desc: "समस्या का विवरण लिखें", phone: "मोबाइल नंबर (अपडेट के लिए)", submit: "शिकायत भेजें",
    nologin: "लॉगिन की जरूरत नहीं · आपकी शिकायत सीधे सड़क एवं भवन विभाग के इंजीनियर तक जाती है", thanks: "धन्यवाद! आपका टिकट नंबर",
    merged: "यह समस्या पहले से दर्ज है — आपकी शिकायत जोड़ दी गई है और इसकी प्राथमिकता बढ़ गई है।", track: "स्थिति देखें",
    another: "दूसरी समस्या बताएं", needpin: "कृपया नक्शे पर स्थान चुनें।", needissue: "कृपया समस्या का प्रकार चुनें।",
    liable: (c: string) => `अच्छी खबर: यह सड़क अभी गारंटी में है। इसे बनाने वाले ठेकेदार ${c} को इसे जनता के किसी खर्च के बिना ठीक करना होगा।`,
    sending: "भेजा जा रहा है…", locating: "आपकी लोकेशन खोजी जा रही है…", noloc: "लोकेशन नहीं मिली — कृपया नक्शे पर टैप करें।",
    issues: { pothole: "गड्ढा", crack: "दरार / टूटी सड़क", waterlogging: "जलभराव", signage: "टूटा बोर्ड", railing: "टूटी रेलिंग", leakage: "इमारत में रिसाव", other: "अन्य" },
  },
};
