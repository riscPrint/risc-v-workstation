import fields from './producer-fields.json';

/** The Python fast tests use this same field list against current producers. */
export function checkProducer(name: keyof typeof fields, value: unknown): void {
 const contract=fields[name], data=(value && typeof value==='object' && !Array.isArray(value) ? value : {}) as Record<string,unknown>;
 if(data.schema!==contract.schema)throw new Error(`Expected ${contract.schema}`);
 for(const [key,type] of Object.entries(contract.fields)) {
   const v=data[key];
   const actual=Array.isArray(v)?'array':v===null?'null':typeof v;
   if(actual!==type)throw new Error(`${contract.schema}.${key}: expected ${type}`);
 }
}
