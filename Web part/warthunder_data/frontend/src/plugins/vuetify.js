// plugins/vuetify.js
import { createVuetify } from 'vuetify'
import { VDataTable, VSelect } from 'vuetify/components'

export default createVuetify({
  components: { VDataTable, VSelect },
  breakpoint: {
    mobileBreakpoint: 'sm',
    thresholds: {
      xs: 0,
      sm: 600,
      md: 960,
      lg: 1280,
      xl: 1920
    }
  }
})