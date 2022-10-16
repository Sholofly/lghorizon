# LG Horizon Settop boxes (Ziggo, Telenet, Magenta, UPC, Virgin)

# WARNING: This is a beta version. It only supports Ziggo (NL). 

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
<br><a href="https://www.buymeacoffee.com/sholofly" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-black.png" width="150px" height="35px" alt="Buy Me A Coffee" style="height: 35px !important;width: 150px !important;" ></a>

## Description

A media player component for Home Assistant that creates a media player and a sensor for each LG Horizon Settopbox in your account.

## Supported Countries and providers

| Country | Provider | Box name | Confirmed working
| --- | ----------- | --- | -----------|
| Netherlands | Ziggo | [Mediabox Next](https://www.ziggo.nl/televisie/mediaboxen/mediabox-next#ziggo-tv) | yes
<!-- | Austria | Magenta | [Entertain box 4K](https://www.magenta.at/entertain-box) | yes
| Switzerland | UPC Switzerland | [UPC TV Box](https://www.upc.ch/en/television/learn-about-tv/tv/) | yes
| Belgium | Telenet | [Telenet TV-Box](https://www2.telenet.be/nl/klantenservice/ontdek-de-telenet-tv-box/) | yes
| Great Britain | Virgin Media | [Virgin TV 360](https://www.virginmedia.com/shop/tv/virgin-tv-360) | yes
| Ireland | Virgin Media | [360 box](https://www.virginmedia.ie/virgintv360support/) | no (testers wanted!) -->



## Not supported countries/providers
Next countries do have the same familiar web interface but aren't supported due to the use of other hardware than the Arris box. 
| Country | Web app URL 
| --- | ----------- 
| Chech Republic | [Horizon TV](https://www.horizon.tv/cs_cz)
| Romania | [Horizon TV](https://www.horizon.tv/ro_ro)
| Slovakia | [Horizon TV](https://www.horizon.tv/sk_sk)
| Germany | [Unknown](https://www.horizon.tv/de_de) | no (testers wanted!)
| Poland | UPC PL | [Unknown](https://www.horizon.tv/pl_pl.html) | no (testers wanted!)
| Hungary | Vodafone Hungary | [Unknown](https://www.horizon.tv/hu_hu.html) | no (testers wanted!)


## Prerequisites

- The energy mode needs to be set to high, otherwise you are not able to switch the device on in the media player.

<!-- ## HACS Installation

1. Make sure you've installed [HACS](https://hacs.xyz/docs/installation/prerequisites)
2. In the integrations tab, search for ArrisDCX960.
3. Install the Integration.
4. Configure the integration using the HA integration page, Search for ArrisDCX960. -->

## Manual installation

1. Open the directory (folder) for your HA configuration (where you find configuration.yaml).
2. If you do not have a custom_components directory (folder) there, you need to create it.
3. In the custom_components directory (folder) create a new folder called arrisdcx960.
4. Download all the files from the custom_components/arrisdcx960/ directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. Configure the integration using the HA integration page, Search for ArrisDCX960.

## Configuration (Example!)

1. In HA Click on settings
2. Click on Integrations
3. Click on button 'Add integration'
4. Search for 'Arris DCX960' and click

### Parameters

| Parameter | Required | Description
| --- | --- | --- |
| Username | yes | Your provider username |
| Password | yes | Your provider password |
| Provider  | yes (default 'Ziggo')| Your Provider |


## Service to change channel

```yaml
service: media_player.play_media
service_data:
  entity_id: media_player.ziggo_beneden
  media_content_id: 401 # Any channel number, 'Netflix' or 'Videoland'
  media_content_type: channel # 'channel' when media_content_id is channelnumber, 'app' when media_content_id is 'Netflix' or 'Videoland' 
```

## Custom services

This service can be called to start a recording. Note that this shows a pop-up on screen and confirmation is required.

```yaml
service: arris_dcx960.record
service_data:
  entity_id: media_player.ziggo_beneden
```

This service can be called to rewind or fast-forward. 
Note that this command can be called multiple times to speed up.
To stop this action, you can call the standard media_player.play service on the same entity.

```yaml
service: arris_dcx960.rewind
service_data:
  entity_id: media_player.ziggo_beneden

service: arris_dcx960.fast_forward
service_data:
  entity_id: media_player.ziggo_beneden
```

This service can be called to emulate a key press on the remote control.

```yaml
service: arris_dcx960.remote_key_press
service_data:
  entity_id: media_player.ziggo_beneden
  remote_key: 'MediaTopMenu'
```
![Key commands](images/remote.png)

## Disclaimer

This component is not provided, supported or maintained by any of the companies named above. They can change their hardware, software or web services at a way that can break this  component. Fingers crossed!
## Credits

- The excellent start from [IIStevowII](https://github.com/IIStevowII/ziggo-mediabox-next) for a single settopbox inspired me!
- The nodejs script [NextRemoteJs from basst85](https://github.com/basst85/NextRemoteJs/) used as reference to compare results.
- The input from [Jochen Siegenthaler](https://github.com/jsiegenthaler/). His [Homebridge](https://github.com/jsiegenthaler/homebridge-eosstb) development helped me forward.
- Contributions by:
  - [shortwood](https://github.com/shortwood)
  - [michael-geerts](https://github.com/michael-geerts)
- Testing by:
  - Craig McGowan (GB)
  - Jarne Roussard (BE)
