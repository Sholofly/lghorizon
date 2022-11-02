
<!-- # LG Horizon Settop boxes (Ziggo, Telenet, Magenta, UPC, Virgin) -->
# LG Horizon Settop boxes for Ziggo(NL), Magenta(AT), UPC(CH), Virgin(IE), Telenet(BE)


[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
<br><a href="https://www.buymeacoffee.com/sholofly" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-black.png" width="150px" height="35px" alt="Buy Me A Coffee" style="height: 35px !important;width: 150px !important;" ></a>

## WARNING: This component replaces the Arris DCX960 component and is in beta status


## Description

A media player component for Home Assistant that controls each LG Horizon Settopbox in your account. After configuration you should see:
- one media player entity for each physical device in your account.
- one sensor entity with the used recording capacity, only if recording is enabled
- Media browser enabled for recordings
- Extended logging
## Supported countries and providers

| Country | Provider | Box name | Confirmed working
| --- | ----------- | --- | -----------|
| Netherlands | Ziggo | [Mediabox Next](https://www.ziggo.nl/televisie/mediaboxen/mediabox-next#ziggo-tv), [Mediabox Next mini](https://www.ziggo.nl/televisie/mediaboxen/next-mini) | yes
| Austria | Magenta | [Entertain box 4K](https://www.magenta.at/entertain-box) | yes
| Switzerland | UPC Switzerland | [UPC TV Box](https://www.upc.ch/en/television/learn-about-tv/tv/) | yes
| Ireland | Virgin Media | [360 box](https://www.virginmedia.ie/virgintv360support/) | no (testers wanted!)
| Belgium | Telenet | [Telenet TV-Box](https://www2.telenet.be/nl/klantenservice/ontdek-de-telenet-tv-box/) | yes
<!--| Great Britain | Virgin Media | [Virgin TV 360](https://www.virginmedia.com/shop/tv/virgin-tv-360) | yes-->
## Prerequisites

- The energy mode needs to be set to high, otherwise you are not able to switch the device on in the media player.

## HACS Installation

1. Make sure you've installed [HACS](https://hacs.xyz/docs/installation/prerequisites)
2. (Temporary) Add this repository to custom repository to HACS
3. In the integrations tab, search for LG Horizon.
4. Install the Integration. Please consider enabling beta versions to keep track of the latest (experimental) features.
5. Configure the integration using the HA integration page, Search for LG Horizon.

## Manual installation

1. Open the directory (folder) for your HA configuration (where you find configuration.yaml).
2. If you do not have a custom_components directory (folder) there, you need to create it.
3. In the custom_components directory (folder) create a new folder called lghorizon.
4. Download all the files from the custom_components/lghorizon/ directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. Configure the integration using the HA integration page, Search for LG Horizon.

## Configuration (Example!)

1. In HA Click on settings
2. Click on Integrations
3. Click on button 'Add integration'
4. Search for 'LG Horizon' and click

### Parameters

| Parameter | Required | Description
| --- | --- | --- |
| Username | yes | Your provider username |
| Password | yes | Your provider password |
| Provider  | yes (default 'Ziggo')| Your Provider |


## Service to change channel

```yaml
service: lghorizon.play_media
service_data:
  entity_id: media_player.ziggo_beneden
  media_content_id: 401 # Any channel number, 'Netflix' or 'Videoland'
  media_content_type: channel # 'channel' when media_content_id is channelnumber, 'app' when media_content_id is 'Netflix' or 'Videoland'
```

## Custom services

This service can be called to start a recording. Note that this shows a pop-up on screen and confirmation is required.

```yaml
service: lghorizon.record
service_data:
  entity_id: media_player.ziggo_beneden
```

This service can be called to rewind or fast-forward.
Note that this command can be called multiple times to speed up.
To stop this action, you can call the standard media_player.play service on the same entity.

```yaml
service: lghorizon.rewind
service_data:
  entity_id: media_player.ziggo_beneden

service: lghorizon.fast_forward
service_data:
  entity_id: media_player.ziggo_beneden
```

This service can be called to emulate a key press on the remote control.

```yaml
service: lghorizon.remote_key_press
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
  - Sammy Verdonck (BE)
