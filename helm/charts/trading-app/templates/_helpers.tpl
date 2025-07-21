{{- define "trading-app.fullname" -}}
{{ include "trading-app.name" . }}
{{- end -}}

{{- define "trading-app.name" -}}
{{ default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "trading-app.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "trading-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "trading-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "trading-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
