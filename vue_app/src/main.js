import Vue from 'vue';

import BootstrapVue from 'bootstrap-vue';
import VueFormWizard from 'vue-form-wizard';
import VueTimeago from 'vue-timeago';

Vue.use(BootstrapVue);
Vue.use(VueFormWizard);
Vue.use(VueTimeago, {name: 'Timeago', locale: 'en'});

import ButtonAdd from './components/misc/ButtonAdd';
import ButtonDelete from './components/misc/ButtonDelete';
import ButtonInfo from './components/misc/ButtonInfo';
import VSelect from './components/misc/VSelect';
import Loading from './components/misc/Loading';
import Property from './components/helpers/Property';
import Card from './components/structural/Card';
import SubCard from './components/structural/SubCard';
import {FontAwesomeIcon} from '@fortawesome/vue-fontawesome';

Vue.component('button-add', ButtonAdd);
Vue.component('button-delete', ButtonDelete);
Vue.component('button-info', ButtonInfo);
Vue.component('v-select', VSelect);
Vue.component('loading', Loading);
Vue.component('property', Property);
Vue.component('card', Card);
Vue.component('sub-card', SubCard);
Vue.component('fa-icon', FontAwesomeIcon);

import {library} from '@fortawesome/fontawesome-svg-core';
import {faQuestionCircle, faClipboard} from '@fortawesome/free-regular-svg-icons';
import {
    faChevronDown, faArrowRight, faPlus, faTrashAlt, faPencilAlt, faCheck, faTimes,
    faInfoCircle, faAlignJustify, faProjectDiagram, faList, faCog
} from '@fortawesome/free-solid-svg-icons';

library.add(faQuestionCircle, faClipboard, faChevronDown, faArrowRight, faPlus, faTrashAlt, faPencilAlt,
    faCheck, faTimes, faInfoCircle, faAlignJustify, faProjectDiagram, faList, faCog);

import md5 from 'md5';

Vue.prototype.$utilities = {
    md5: md5,

    getOrCreate(setter, subject, key, default_value) {
        if (typeof subject[key] === 'undefined')
            setter(subject, key, default_value);

        return subject[key];
    },
};

Vue.filter('capitalize', function (value) {
    if (!value) return '';
    value = value.toString();
    return value.charAt(0).toUpperCase() + value.slice(1);
});

import App from './App.vue';
import JobMixin from './mixins/JobMixin';

import './assets/app.scss';
import 'vue-form-wizard/dist/vue-form-wizard.min.css';

new Vue({
    mixins: [JobMixin],
    render: h => h(App),
}).$mount('#app');
