// The line breaker (UAX #14) ships without types.
declare module 'linebreak' {
  interface Break {
    position: number
    required: boolean
  }
  export default class LineBreaker {
    constructor(text: string)
    nextBreak(): Break | null
  }
}
