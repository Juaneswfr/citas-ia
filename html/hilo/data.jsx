// hilo/data.jsx — realistic barbershop mock data (es-CO)
const HILO = {};

HILO.business = {
  name: 'Navaja & Tinta',
  kind: 'Barbería',
  city: 'Medellín · El Poblado',
  tz: 'America/Bogotá',
  phone: '+57 304 218 9930',
  hours: 'Lun–Sáb · 9:00 a 20:00',
};

HILO.owner = { name: 'Camilo Restrepo', role: 'Dueño', initials: 'CR' };

// service / line-of-work hues map to CSS vars
HILO.services = [
  { id:'s1', name:'Corte clásico',        dur:40, buffer:5,  price:38000, home:false, extra:0,     active:true,  hue:'clay',    pros:['Andrés','Julián'], book:128 },
  { id:'s2', name:'Corte + barba',        dur:60, buffer:10, price:55000, home:false, extra:0,     active:true,  hue:'wine',    pros:['Andrés','Julián','Samuel'], book:204 },
  { id:'s3', name:'Arreglo de barba',     dur:25, buffer:5,  price:25000, home:false, extra:0,     active:true,  hue:'mustard', pros:['Julián','Samuel'], book:96 },
  { id:'s4', name:'Afeitado a navaja',    dur:35, buffer:10, price:42000, home:false, extra:0,     active:true,  hue:'steel',   pros:['Andrés'], book:54 },
  { id:'s5', name:'Corte a domicilio',    dur:50, buffer:20, price:38000, home:true,  extra:20000, active:true,  hue:'sage',    pros:['Samuel'], book:31 },
  { id:'s6', name:'Tinte y color',        dur:90, buffer:15, price:90000, home:false, extra:0,     active:false, hue:'plum',    pros:['Julián'], book:12 },
];

HILO.team = [
  { id:'b1', name:'Andrés Vélez',   initials:'AV', role:'Barbero senior', cal:true,  last:'hace 4 min',  hue:'clay' },
  { id:'b2', name:'Julián Mora',    initials:'JM', role:'Barbero',        cal:true,  last:'hace 18 min', hue:'wine' },
  { id:'b3', name:'Samuel Ríos',    initials:'SR', role:'Barbero · domic.',cal:false, last:'ayer',       hue:'sage' },
];

// today's appointments (the "day as a story" thread)
HILO.today = [
  { id:'a1', time:'09:00', end:'09:40', client:'Mateo Gómez',     svc:'Corte clásico',     pro:'Andrés', status:'done',    via:'wa',     phone:'+57 311 555 0142' },
  { id:'a2', time:'09:45', end:'10:45', client:'Daniel Ospina',   svc:'Corte + barba',     pro:'Julián', status:'done',    via:'manual', phone:'+57 300 555 0119' },
  { id:'a3', time:'11:00', end:'11:25', client:'Sebastián Ruiz',  svc:'Arreglo de barba',  pro:'Samuel', status:'now',     via:'wa',     phone:'+57 304 555 0188' },
  { id:'a4', time:'12:00', end:'12:35', client:'Tomás Cardona',   svc:'Afeitado a navaja', pro:'Andrés', status:'next',    via:'wa',     phone:'+57 312 555 0177' },
  { id:'a5', time:'14:30', end:'15:30', client:'Felipe Arango',   svc:'Corte + barba',     pro:'Julián', status:'upcoming',via:'wa',     phone:'+57 305 555 0163' },
  { id:'a6', time:'16:00', end:'16:50', client:'Nicolás Bedoya',  svc:'Corte a domicilio', pro:'Samuel', status:'upcoming',via:'wa',     phone:'+57 318 555 0154', home:true },
  { id:'a7', time:'18:00', end:'19:00', client:'Esteban Lopera',  svc:'Corte + barba',     pro:'Andrés', status:'upcoming',via:'manual', phone:'+57 301 555 0131' },
];

HILO.metrics = {
  todayCount: 7, doneCount: 2, upcomingCount: 4,
  revenueMonth: 6480000, revenuePrev: 5710000,
  automation: 86, // %
  cancels: 2,
  responseAvg: '41 s',
};

HILO.clients = [
  { id:'c1', name:'Felipe Arango',  phone:'+57 305 555 0163', last:'hace 3 días', next:'Hoy · 14:30', visits:14, fav:'Corte + barba',    spend:770000, status:'frecuente', note:'Prefiere a Julián. Tijera, no máquina en los lados.' },
  { id:'c2', name:'Mateo Gómez',    phone:'+57 311 555 0142', last:'Hoy · 09:00', next:'—',           visits:8,  fav:'Corte clásico',    spend:304000, status:'activo',    note:'Llega 10 min antes siempre.' },
  { id:'c3', name:'Nicolás Bedoya', phone:'+57 318 555 0154', last:'hace 1 mes',  next:'Hoy · 16:00', visits:5,  fav:'Corte a domicilio',spend:290000, status:'activo',    note:'Domicilio en Laureles, torre 2 apto 901.' },
  { id:'c4', name:'Daniel Ospina',  phone:'+57 300 555 0119', last:'Hoy · 09:45', next:'—',           visits:21, fav:'Corte + barba',    spend:1155000,status:'VIP',       note:'Cliente desde 2023. Café sin azúcar.' },
  { id:'c5', name:'Sebastián Ruiz', phone:'+57 304 555 0188', last:'Hoy · 11:00', next:'—',           visits:3,  fav:'Arreglo de barba', spend:75000,  status:'nuevo',     note:'' },
  { id:'c6', name:'Tomás Cardona',  phone:'+57 312 555 0177', last:'hace 2 sem',  next:'Hoy · 12:00', visits:6,  fav:'Afeitado a navaja',spend:252000, status:'activo',    note:'Alérgico a lociones con alcohol.' },
];

// live agent conversation (dashboard right panel)
HILO.conversation = {
  client:'Felipe Arango', phone:'+57 305 555 0163', intent:'Reagendar cita',
  msgs:[
    { from:'client', t:'09:58', text:'Hola, tengo cita hoy a las 2:30 pero me salió algo. La puedo mover?' },
    { from:'agent',  t:'09:58', text:'¡Claro, Felipe! Tu cita de Corte + barba con Julián es hoy a las 2:30 pm. ¿Para cuándo te gustaría moverla?' },
    { from:'client', t:'09:59', text:'Mañana en la tarde si se puede' },
    { from:'agent',  t:'09:59', text:'Tengo estos espacios con Julián mañana: 3:00 pm, 4:15 pm o 6:00 pm. ¿Cuál te sirve?' },
    { from:'client', t:'10:00', text:'4:15 perfecto' },
  ],
  action:{ label:'Cita reagendada · mañana 16:15', sub:'Corte + barba · Julián' },
};

HILO.alerts = [
  { id:'al1', kind:'warning', icon:'sync',  text:'Google Calendar de Samuel sin sincronizar', sub:'Última sync hace 2 h', cta:'Reconectar' },
  { id:'al2', kind:'info',    icon:'sparkle',text:'El agente no entendió 1 mensaje hoy',       sub:'“quiero lo de siempre” · Sebastián R.', cta:'Revisar' },
];

HILO.channel = { number:'+57 304 218 9930', provider:'WhatsApp Cloud API', coexistence:true, status:'activo', lastSync:'hace 1 min' };

// helpers
HILO.fmtCOP = (n) => '$' + n.toLocaleString('es-CO');
HILO.hueVar = (h) => h === 'wine' ? 'var(--wine)' : `var(--${h})`;

window.HILO = HILO;
